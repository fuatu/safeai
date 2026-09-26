#!/usr/bin/env bash
# ==============================================================================
# SafeAI Shell Integration Hook (Zsh & Bash)
# Pre-execution security interception for AI Agent Terminal Executions
# ==============================================================================

SAFEAI_GATE_BIN="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)/safeai-gate"
export SAFEAI_GATEWAY_URL="${SAFEAI_GATEWAY_URL:-http://localhost:8080/api/eval/intercept}"

safeai_preexec_check() {
    local cmd="$1"

    # Skip empty or internal check commands
    if [[ -z "$cmd" || "$cmd" == safeai* || "$cmd" == "clear" || "$cmd" == "pwd" ]]; then
        return 0
    fi

    # Query SafeAI Gate
    if [[ -x "$SAFEAI_GATE_BIN" ]]; then
        "$SAFEAI_GATE_BIN" --eval "$cmd"
        local ret=$?
        if [[ $ret -ne 0 ]]; then
            # Command was blocked by SafeAI
            return $ret
        fi
    fi
    return 0
}

# ------------------------------------------------------------------------------
# Zsh Integration (using preexec_functions hook)
# ------------------------------------------------------------------------------
if [[ -n "$ZSH_VERSION" ]]; then
    safeai_zsh_preexec() {
        safeai_preexec_check "$1"
    }

    # Add to zsh preexec hooks if not already present
    if [[ ! " ${preexec_functions[*]} " =~ " safeai_zsh_preexec " ]]; then
        preexec_functions+=(safeai_zsh_preexec)
    fi
    echo "🛡️  SafeAI Shell Gate active (Zsh). Real-time CIA Triad protection enabled."

# ------------------------------------------------------------------------------
# Bash Integration (using DEBUG trap)
# ------------------------------------------------------------------------------
elif [[ -n "$BASH_VERSION" ]]; then
    safeai_bash_trap() {
        # Check command before running
        safeai_preexec_check "$BASH_COMMAND"
    }
    trap 'safeai_bash_trap' DEBUG
    echo "🛡️  SafeAI Shell Gate active (Bash). Real-time CIA Triad protection enabled."
fi
