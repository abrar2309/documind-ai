# Stage 5 — Production security baseline

## Implemented by this patch

- Environment-aware FastAPI documentation exposure (disabled in production).
- Exact-origin CORS configuration; no wildcard credentials policy.
- Configurable trusted-host allowlist.
- Production configuration validation: long non-placeholder JWT secret, HTTPS CORS origins, explicit origins, API docs disabled.
- Security response headers and HSTS when HTTPS is observed at the trusted reverse proxy.
- Backend container runs as an unprivileged user.
- Frontend Nginx adds baseline security headers, hides its version, limits upload body size, and caches fingerprinted assets.
- `.env` and local secrets remain excluded from source control.

## Required before public launch

1. Put secrets in AWS Secrets Manager or SSM Parameter Store SecureString; never in GitHub variables or Terraform state.
2. Rotate all credentials that have ever been committed, pasted into chat, or shared in logs.
3. Configure HTTPS at an Application Load Balancer or CloudFront with an ACM certificate.
4. Set `ENVIRONMENT=production`, `EXPOSE_API_DOCS=false`, `CORS_ALLOWED_ORIGINS=https://<real-frontend-domain>`, and `TRUSTED_HOSTS=<real-hostnames>`.
5. Use a production-grade JWT secret (32+ random characters).
6. Review authentication token storage. The current frontend stores access and refresh tokens in `localStorage`; this is not an HttpOnly-cookie architecture. Mitigate XSS and plan a dedicated secure-cookie/CSRF migration before handling sensitive production workloads.
7. Add WAF, alerting, vulnerability scanning, backup/restore drills, rate-limit policy review, and incident response ownership.

## Explicit non-claims

This patch does not constitute a penetration test, compliance certification, WAF deployment, secrets rotation, or proof of secure cookie authentication.
