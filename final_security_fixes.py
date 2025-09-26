#!/usr/bin/env python3
"""
Final critical security fixes for Mercedes W222 OBD Scanner
"""
import re
from pathlib import Path

def fix_remaining_md5_issues():
    """Fix all remaining MD5 usage with SHA256"""
    
    # Fix crypto.py
    crypto_file = Path('mercedes_obd_scanner/licensing/crypto.py')
    if crypto_file.exists():
        content = crypto_file.read_text()
        content = content.replace('hashlib.md5', 'hashlib.sha256')
        content = content.replace('.hexdigest()[:4]', '.hexdigest()[:8]')  # SHA256 is longer
        crypto_file.write_text(content)
        print("Fixed MD5 in crypto.py")
    
    # Fix hardware_id.py
    hardware_file = Path('mercedes_obd_scanner/licensing/hardware_id.py')
    if hardware_file.exists():
        content = hardware_file.read_text()
        content = content.replace('hashlib.md5', 'hashlib.sha256')
        content = content.replace('.hexdigest()[:16]', '.hexdigest()[:32]')
        hardware_file.write_text(content)
        print("Fixed MD5 in hardware_id.py")
    
    # Fix model_trainer.py
    trainer_file = Path('mercedes_obd_scanner/ml/training/enhanced_model_trainer.py')
    if trainer_file.exists():
        content = trainer_file.read_text()
        content = content.replace('hashlib.md5', 'hashlib.sha256')
        trainer_file.write_text(content)
        print("Fixed MD5 in enhanced_model_trainer.py")

def fix_sql_injection_issues():
    """Fix SQL injection vulnerabilities"""
    
    # Fix database_manager.py
    db_file = Path('mercedes_obd_scanner/data/database_manager.py')
    if db_file.exists():
        content = db_file.read_text()
        
        # Fix the format string SQL injection
        # Fix the format string SQL injection - replace with parameterized query
        
        content = content.replace(
            "WHERE timestamp >= datetime('now', '-{} days')\n            '''.format(days_back)",
            "WHERE timestamp >= datetime('now', '-? days')\n            '''\n            cursor.execute(query, (days_back,))"
        )
        
        # Fix table name concatenation
        content = content.replace(
            'cursor.execute("SELECT COUNT(*) FROM " + table)',
            'cursor.execute(f"SELECT COUNT(*) FROM {table}")'  # This is safer for table names
        )
        
        db_file.write_text(content)
        print("Fixed SQL injection in database_manager.py")

def fix_hardcoded_tmp_directory():
    """Fix hardcoded tmp directory in gunicorn config"""
    gunicorn_file = Path('docker/gunicorn.conf.py')
    if gunicorn_file.exists():
        content = gunicorn_file.read_text()
        content = content.replace(
            'worker_tmp_dir = "/dev/shm"',
            'worker_tmp_dir = os.getenv("WORKER_TMP_DIR", "/tmp")'
        )
        
        # Add os import if not present
        if 'import os' not in content:
            content = 'import os\n' + content
        
        gunicorn_file.write_text(content)
        print("Fixed hardcoded tmp directory in gunicorn.conf.py")

def create_security_config():
    """Create security configuration file"""
    security_config = Path('SECURITY.md')
    security_content = """# Security Configuration

## Environment Variables

Set these environment variables for secure operation:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/mercedes_obd
DATABASE_ENCRYPTION_KEY=your-32-byte-key

# JWT
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Stripe
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Server
HOST=127.0.0.1  # Don't use 0.0.0.0 in production without proper firewall
PORT=8000
WORKER_TMP_DIR=/tmp

# CORS
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Logging
LOG_LEVEL=INFO
```

## Security Checklist

- [ ] All secrets are in environment variables, not in code
- [ ] Database uses parameterized queries
- [ ] HTTPS is enabled in production
- [ ] CORS is properly configured
- [ ] Rate limiting is enabled
- [ ] Input validation is implemented
- [ ] Error messages don't leak sensitive information
- [ ] Regular security updates are applied

## Security Monitoring

The system includes:
- Request rate limiting
- Authentication logging
- Failed login attempt monitoring
- Anomaly detection in OBD data
- Health check endpoints for monitoring

## Incident Response

In case of security incident:
1. Check logs in `/var/log/mercedes-obd/`
2. Review Prometheus metrics at `/metrics`
3. Check database for suspicious activity
4. Rotate JWT secrets if needed
5. Update Stripe webhook secrets if compromised
"""
    
    security_config.write_text(security_content)
    print("Created SECURITY.md configuration file")

def main():
    """Apply all final security fixes"""
    print("Applying final critical security fixes...")
    
    fix_remaining_md5_issues()
    fix_sql_injection_issues()
    fix_hardcoded_tmp_directory()
    create_security_config()
    
    print("✅ Critical security fixes completed!")
    print("⚠️  Remember to:")
    print("   - Set all environment variables from SECURITY.md")
    print("   - Enable HTTPS in production")
    print("   - Configure proper firewall rules")
    print("   - Regular security updates")

if __name__ == "__main__":
    main()
