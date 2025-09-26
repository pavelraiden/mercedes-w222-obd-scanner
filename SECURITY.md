# Security Configuration

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
