# Domain Structure and SSL Management

## Overview

This document defines the domain structure and SSL/TLS certificate management strategy for `livingcontent.co`. The SAN (Subject Alternative Name) certificate method, combined with wildcard entries, is used to secure current and future subdomains. This approach ensures clarity, control, and scalability for new subdomains.

## Domain Structure

The following domain structure has been defined:

### Project Domains

- Production:
  - `project-<project_id>.api.livingcontent.co` – Main API endpoint.

- Staging:
  - `project-<project_id>-stage.api.livingcontent.co` – Staging environment for the API.

## SSL/TLS Strategy

### SAN Certificate

The SAN certificate method is used to secure the current and future subdomains of `livingcontent.co`. This approach involves listing specific domains and wildcard entries explicitly within the certificate's Subject Alternative Name field.

### Certificate Details

The SAN certificate will include the following:

1. `*.livingcontent.co`:
   - `api.livingcontent.co`
   - Any other first-level subdomains, such as `docs.livingcontent.co`.

2. `*.api.livingcontent.co`:
   - Any subdomains under `api.livingcontent.co`.

## AWS Implementation & Automation

If you're using AWS for domain management, the following AWS-native steps can be implemented:

1. AWS Certificate Manager (ACM):
   - Certificates will be managed through AWS Certificate Manager.
   - ACM supports SAN certificates with wildcard entries, allowing flexible coverage of all subdomains.
   - ACM automates the issuance and renewal process for certificates used with AWS services like CloudFront.

2. No Manual Addition for Covered Subdomains:
   - Subdomains under `*.api.livingcontent.co` (e.g., `demo.api.livingcontent.co`, `test.api.livingcontent.co`) will automatically be covered by the wildcard entry.
   - Only new root-level subdomains (e.g., `newsubdomain.livingcontent.co`) or subdomains requiring specific control will require manual addition.

3. DNS Validation:
   - ACM will use Route 53 DNS validation to verify domain ownership.

### Process for Adding Future Subdomains

No manual action is required for subdomains under `api.livingcontent.co` due to the wildcard entry (`*.api.livingcontent.co`).

For subdomains outside of `api.livingcontent.co` (e.g., `docs.livingcontent.co`):

1. Add the new subdomain to the SAN list in AWS Certificate Manager (ACM) via the AWS Management Console, CLI, or API.
2. ACM will automatically handle reissuing the certificate with the updated SAN list.
3. The updated certificate will be propagated to the associated AWS resources.
