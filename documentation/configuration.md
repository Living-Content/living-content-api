# Configuration

## Environment Configuration

Configuration is managed through YAML files in three environments:

- Development
- Staging
- Production

## Configuration Files

### Main Configuration

- Located in `/config`
- Environment-specific settings
- API configuration
- Database settings
- Cache settings

### Ingress Configuration

- URL specifications
- Port settings
- SSL/TLS settings

### Secrets Management

1. Secret Files
   - Located in `/secrets`
   - Environment-specific secrets
   - API keys
   - Authentication tokens

2. Generate Secrets

   ```bash
   ./lc.sh secrets:generate
   ```

## Environment Variables

- Generated from configuration files
- Managed through `.env` file
- Regenerate after config changes:

```bash
./lc.sh env:generate
```

## Important Notes

1. Always regenerate `.env` after configuration changes
2. Docker volumes are rebuilt on configuration changes
3. SSL certificates must match allowed URLs in configuration
4. Configuration changes require container rebuild
