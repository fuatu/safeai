import { useEffect, useRef, useState, useCallback } from 'react';
import { PendingApprovalEvent } from '../types';

interface UseSafeAIWebSocketOptions {
  onActionLogged?: (data: any) => void;
}

interface UseSafeAIWebSocketReturn {
  isConnected: boolean;
  pendingApprovals: PendingApprovalEvent[];
  submitDecision: (actionId: string, decision: 'APPROVE' | 'DENY', notes?: string) => Promise<void>;
  dismissApproval: (actionId: string) => void;
}

export function useSafeAIWebSocket(options?: UseSafeAIWebSocketOptions): UseSafeAIWebSocketReturn {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [pendingApprovals, setPendingApprovals] = useState<PendingApprovalEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const onActionLoggedRef = useRef(options?.onActionLogged);

  useEffect(() => {
    onActionLoggedRef.current = options?.onActionLogged;
  }, [options?.onActionLogged]);

  // Play audio chime using Web Audio API (Req 5.2: zero external asset dependency)
  const playAlertChime = useCallback(() => {
    try {
      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      if (!AudioContextClass) return;
      const ctx = new AudioContextClass();

      // Dual-tone high priority security chime
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.type = 'sine';
      osc2.type = 'triangle';

      osc1.frequency.setValueAtTime(880, ctx.currentTime); // A5
      osc1.frequency.exponentialRampToValueAtTime(1320, ctx.currentTime + 0.15); // E6

      osc2.frequency.setValueAtTime(440, ctx.currentTime);
      osc2.frequency.exponentialRampToValueAtTime(660, ctx.currentTime + 0.15);

      gain.gain.setValueAtTime(0.3, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.4);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);

      osc1.start();
      osc2.start();
      osc1.stop(ctx.currentTime + 0.45);
      osc2.stop(ctx.currentTime + 0.45);
    } catch {
      // AudioContext could be blocked by autoplay policies
    }
  }, []);

  // Request browser desktop notification permission
  useEffect(() => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  const triggerNotification = useCallback((event: PendingApprovalEvent) => {
    // If document is hidden or inactive, trigger sound & desktop notification (Req 5.2)
    playAlertChime();
    if (document.hidden && 'Notification' in window && Notification.permission === 'granted') {
      new Notification('🚨 SafeAI Action Approval Required', {
        body: `[Risk: ${event.riskScore}/100] ${event.plainExplanation}`,
        icon: '/favicon.ico',
      });
    }
  }, [playAlertChime]);

  // Connect WebSocket
  useEffect(() => {
    let unmounted = false;

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmounted) return;
        setIsConnected(true);
      };

      ws.onmessage = (messageEvent) => {
        if (unmounted) return;
        try {
          const data = JSON.parse(messageEvent.data);

          if (data.type === 'PENDING_APPROVAL') {
            const approval = data as PendingApprovalEvent;
            setPendingApprovals((prev) => {
              if (prev.some((p) => p.actionId === approval.actionId)) {
                return prev;
              }
              return [...prev, approval];
            });
            triggerNotification(approval);
          } else if (data.type === 'APPROVAL_RESOLVED') {
            setPendingApprovals((prev) => prev.filter((p) => p.actionId !== data.actionId));
          } else if (data.type === 'ACTION_LOGGED') {
            onActionLoggedRef.current?.(data);
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onclose = () => {
        if (unmounted) return;
        setIsConnected(false);
        // Exponential backoff reconnect
        reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    // Also poll REST pending once at start to ensure sync
    fetch('/api/approvals/pending')
      .then((res) => (res.ok ? res.json() : []))
      .then((items: PendingApprovalEvent[]) => {
        if (!unmounted && Array.isArray(items) && items.length > 0) {
          setPendingApprovals((prev) => {
            const combined = [...prev];
            for (const item of items) {
              if (!combined.some((c) => c.actionId === item.actionId)) {
                combined.push(item);
              }
            }
            return combined;
          });
        }
      })
      .catch(() => {});

    return () => {
      unmounted = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [triggerNotification]);

  const submitDecision = useCallback(async (actionId: string, decision: 'APPROVE' | 'DENY', notes?: string) => {
    // Optimistic UI removal
    setPendingApprovals((prev) => prev.filter((p) => p.actionId !== actionId));

    // Try WebSocket first
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          type: 'DECISION',
          actionId,
          decision,
          notes,
        })
      );
    } else {
      // Fallback to REST
      await fetch('/api/approvals/decide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actionId, decision, notes }),
      });
    }
  }, []);

  const dismissApproval = useCallback((actionId: string) => {
    setPendingApprovals((prev) => prev.filter((p) => p.actionId !== actionId));
  }, []);

  return {
    isConnected,
    pendingApprovals,
    submitDecision,
    dismissApproval,
  };
}
