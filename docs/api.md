# API Authentication and Integration Guide

This guide explains the three ways to interact with the Living Content API:

1. Direct API Access (API Key only)
2. Authentication Provider Integration
3. Direct User Management

## Table of Contents

- [API Authentication and Integration Guide](#api-authentication-and-integration-guide)
  - [Table of Contents](#table-of-contents)
  - [Simple API Access](#simple-api-access)
    - [Setup](#setup)
    - [Making Requests](#making-requests)
  - [Authentication Provider Integration](#authentication-provider-integration)
    - [Provider Setup](#provider-setup)
    - [Authentication Flow](#authentication-flow)
  - [Direct User Management](#direct-user-management)
    - [User Creation Flow](#user-creation-flow)
  - [Content Sessions](#content-sessions)
  - [CORS Configuration](#cors-configuration)
    - [Server-to-Server Communication](#server-to-server-communication)
  - [Error Handling](#error-handling)
    - [Common Status Codes](#common-status-codes)

## Simple API Access

The simplest way to use the API is with an API key for direct endpoint access. This method:

- Doesn't use Living Content's user management
- Doesn't store session data
- Requires you to manage your own users and sessions
- Best for simple integrations or testing

### Setup

1. Obtain an API key
2. Store it in your secrets configuration:

```yaml
api_key: "your_api_key"
```

### Making Requests

Include your API key in the `X-API-Key` header:

```bash
# Example query submission
curl -X POST https://api.example.com/query/submit \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "your query data"}'
```

## Authentication Provider Integration

Auth providers can leverage Living Content's user and session management while using their own user IDs. This method:

- Uses Living Content's session management
- Stores user data and sessions
- Maps your user IDs to Living Content's system
- Best for full platform integration

As an auth provider you will need to store the user's Content Session ID(s) and User Access Token.

### Provider Setup

1. Register as an auth provider and receive a provider secret
2. Add to secrets configuration:

```yaml
auth-providers_your_provider_name: "your_provider_secret"
```

### Authentication Flow

1. Authenticate User as an Auth Provider

   ```bash
   curl -X POST https://api.example.com/user/auth \
     -H "X-Auth-Provider: your_provider_name" \
     -H "X-Auth-User-ID: your_user_id" \
     -H "Authorization: Bearer your_provider_secret"
   ```

   Response for new user:

   ```json
   {
       "userId": "generated_internal_id",
       "accessToken": "generated_access_token",
       "isNewUser": true
   }
   ```

   Response for existing user:

   ```json
   {
       "userId": "existing_internal_id",
       "accessToken": "existing_access_token",
       "isNewUser": false
   }
   ```

2. Using the API as an Auth Provider

   ```bash
   # Create content session
   curl -X POST https://api.example.com/content-session/create \
     -H "X-Auth-Provider: your_provider_name" \
     -H "X-Auth-User-ID: your_user_id" \
     -H "Authorization: Bearer your_provider_secret"

   # Submit query with session
   curl -X POST https://api.example.com/query/submit \
     -H "X-Auth-Provider: your_provider_name" \
     -H "X-Auth-User-ID: your_user_id" \
     -H "Authorization: Bearer your_provider_secret" \
     -H "X-Content-Session-ID: received_session_id" \
     -d '{"query": "your query"}'
   ```

## Direct User Management

Use Living Content's built-in user management system. This method:

- Uses Living Content's user management
- Stores user data and sessions
- Best for applications without existing user management

### User Creation Flow

1. Generate User Creation Token

   ```bash
   curl -X POST https://api.example.com/access-token/user-creation-token/create
   ```

   Response:

   ```json
   {
       "userCreationToken": {
           "accessToken": "generated_token"
       }
   }
   ```

2. Create User

   ```bash
   curl -X POST https://api.example.com/user/create \
     -H "Authorization: Bearer generated_token"
   ```

   Response:

   ```json
   {
       "userId": "generated_user_id"
   }
   ```

3. Using the API

   ```bash
   # All subsequent requests
   curl -X POST https://api.example.com/query/submit \
     -H "Authorization: Bearer access_token" \
     -H "X-User-ID: user_id" \
     -H "X-Content-Session-ID: session_id" \
     -d '{"query": "your query"}'
   ```

## Content Sessions

Content sessions are required when using auth provider or direct user management:

```bash
# Create session
curl -X POST https://api.example.com/content-session/create \
  -H "Authorization: Bearer your_access_token" \
  -H "X-User-ID: user_id"

# Get session data
curl -X GET https://api.example.com/content-session/get-data \
  -H "Authorization: Bearer your_access_token" \
  -H "X-User-ID: user_id" \
  -H "X-Content-Session-ID: session_id"
```

Not required for simple API access with API key.

## CORS Configuration

Configure allowed origins in your config:

```yaml
ingress:
  allowed_origins: 
    - "https://your-domain.com"
    - "https://app.your-domain.com"
```

### Server-to-Server Communication

Bypass CORS checks by:

- Using an API key
- Including an x-webhook-secret
- Not including an Origin header

## Error Handling

Standard HTTP status codes with consistent response format:

```json
{
    "status": "error",
    "data": "error_code",
    "message": "Error description"
}
```

Success response format:

```json
{
    "status": "success",
    "data": "success_code",
    "message": "Success description"
}
```

### Common Status Codes

- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Internal Server Error
