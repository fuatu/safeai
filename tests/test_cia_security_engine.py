"""Comprehensive test suite for Autonomous CIA Triad and Data Loss Security Scoring."""

import pytest
from backend.security.engine import SecurityEngine


@pytest.fixture
def engine():
    return SecurityEngine()


def test_file_data_loss_integrity(engine):
    # Single file deletion
    res_single = engine.evaluate_payload("bash", {"command": "rm -f ./data/safeai.db"})
    assert res_single.risk_score >= 70
    assert res_single.integrity_score >= 70
    assert any("destructive" in f or "critical_file" in f for f in res_single.risk_factors)

    # Recursive root delete
    res_rec = engine.evaluate_payload("bash", {"command": "rm -rf /etc/config"})
    assert res_rec.risk_score >= 90
    assert res_rec.integrity_score >= 90

    # Unlink & file truncation
    res_unlink = engine.evaluate_payload("bash", {"command": "unlink /tmp/database.sqlite"})
    assert res_unlink.integrity_score >= 70

    res_trunc = engine.evaluate_payload("bash", {"command": "truncate -s 0 ./data/audit.db"})
    assert res_trunc.integrity_score >= 80

    res_find_del = engine.evaluate_payload("bash", {"command": "find . -name '*.db' -delete"})
    assert res_find_del.integrity_score >= 85


def test_sql_database_data_loss_integrity(engine):
    # Direct SQL
    res_del = engine.evaluate_payload("bash", {"command": "DELETE FROM sessions WHERE id = 1"})
    assert res_del.risk_score >= 80
    assert res_del.integrity_score >= 80
    assert "[Integrity] sql_delete_from_table" in res_del.risk_factors

    res_drop = engine.evaluate_payload("bash", {"command": "DROP TABLE action_logs"})
    assert res_drop.risk_score >= 90
    assert res_drop.integrity_score >= 90
    assert "[Integrity] sql_drop_table_or_database" in res_drop.risk_factors

    res_trunc = engine.evaluate_payload("bash", {"command": "TRUNCATE TABLE users"})
    assert res_trunc.risk_score >= 85
    assert res_trunc.integrity_score >= 85

    # CLI Client
    res_sqlite = engine.evaluate_payload("bash", {"command": "sqlite3 safeai.db \"DELETE FROM sessions;\""})
    assert res_sqlite.risk_score >= 80
    assert "[Integrity] sql_delete_from_table" in res_sqlite.risk_factors

    # Embedded in python script
    res_embedded = engine.evaluate_payload(
        "bash",
        {"command": "python3 -c \"import sqlite3; cur.executescript('DELETE FROM action_logs; DELETE FROM sessions;')\""},
    )
    assert res_embedded.risk_score >= 80
    assert "[Integrity] sql_delete_from_table" in res_embedded.risk_factors


def test_cloud_infrastructure_integrity(engine):
    # AWS S3 file delete
    res_s3 = engine.evaluate_payload("bash", {"command": "aws s3 rm s3://company-backups/db.tar.gz"})
    assert res_s3.risk_score >= 85
    assert "[Integrity] aws_s3_delete" in res_s3.risk_factors

    # AWS EC2 terminate
    res_ec2 = engine.evaluate_payload("bash", {"command": "aws ec2 terminate-instances --instance-ids i-12345"})
    assert res_ec2.risk_score >= 90
    assert "[Integrity] aws_ec2_terminate" in res_ec2.risk_factors

    # Azure Resource Group delete
    res_az = engine.evaluate_payload("bash", {"command": "az group delete --name production-rg --yes"})
    assert res_az.risk_score >= 95
    assert "[Integrity] az_resource_group_delete" in res_az.risk_factors

    # GCP compute instance delete
    res_gcp = engine.evaluate_payload("bash", {"command": "gcloud compute instances delete prod-server --zone us-central1-a"})
    assert res_gcp.risk_score >= 90
    assert "[Integrity] gcloud_instance_delete" in res_gcp.risk_factors

    # Kubernetes delete namespace
    res_k8s = engine.evaluate_payload("bash", {"command": "kubectl delete namespace production"})
    assert res_k8s.risk_score >= 85
    assert "[Integrity] k8s_delete_resource" in res_k8s.risk_factors

    # Terraform destroy
    res_tf = engine.evaluate_payload("bash", {"command": "terraform destroy -auto-approve"})
    assert res_tf.risk_score >= 95
    assert "[Integrity] terraform_destroy" in res_tf.risk_factors


def test_confidentiality_cloud_and_secrets(engine):
    # AWS Secrets Manager
    res_sec = engine.evaluate_payload("bash", {"command": "aws secretsmanager get-secret-value --secret-id prod/db"})
    assert res_sec.risk_score >= 85
    assert res_sec.confidentiality_score >= 85
    assert "[Confidentiality] aws_secretsmanager_read" in res_sec.risk_factors

    # Azure KeyVault
    res_kv = engine.evaluate_payload("bash", {"command": "az keyvault secret show --name api-key --vault-name myvault"})
    assert res_kv.risk_score >= 85
    assert res_kv.confidentiality_score >= 85
    assert "[Confidentiality] az_keyvault_secret_read" in res_kv.risk_factors

    # Local .env
    res_env = engine.evaluate_payload("bash", {"command": "cat .env.production"})
    assert res_env.confidentiality_score >= 80


def test_availability_threats(engine):
    # Force kill
    res_kill = engine.evaluate_payload("bash", {"command": "killall -9 uvicorn"})
    assert res_kill.risk_score >= 80
    assert res_kill.availability_score >= 80
    assert any("force_kill" in f or "process" in f for f in res_kill.risk_factors)

    # Docker compose volume teardown
    res_down = engine.evaluate_payload("bash", {"command": "docker compose down -v"})
    assert res_down.risk_score >= 85
    assert res_down.availability_score >= 85
    assert "[Availability] docker_compose_down_volumes" in res_down.risk_factors

    # System reboot / shutdown
    res_reboot = engine.evaluate_payload("bash", {"command": "shutdown -h now"})
    assert res_reboot.risk_score >= 95
    assert res_reboot.availability_score >= 95


def test_safe_developer_commands_pass(engine):
    safe_cmds = [
        "git status",
        "git diff",
        "ls -la",
        "npm run build",
        "npm test",
        "pytest tests/",
        "python3 -m unittest",
        "echo 'Hello world'",
        "cat README.md",
    ]
    for cmd in safe_cmds:
        res = engine.evaluate_payload("bash", {"command": cmd})
        assert res.risk_score < 50, f"Expected safe for '{cmd}', got {res.risk_score}"
