# Database Schemas Documentation

## Redis Schemas

### User

```json
{
  "user:UUID4": {
    "accessToken": "UUID4",
    "permissionsToken": "UUID4",
    "requests": {
      "lastMinute": 0,
      "lastDay": 0,
      "allTime": 0
    },
    "verified": false
  }
}
```

### User Creation Token

```json
{
  "accessToken:UUID4": {
    "userId": "UUID4",
    "createdAt": "datetime"
  }
}
```

## MongoDB Schemas

### Users Collection

```json
{
  "_id": "UUID4",
  "accessToken": "UUID4",
  "permissionsToken": "UUID4",
  "activeContentSessionId": "UUID4",
  "createdAt": "datetime",
  "lastAccessed": "datetime",
  "requests": {
    "allTime": 0
  },
  "unreadNotifications": {},
  "authProviders": {},
  "verified": false,
  "emailAddress": "string or null",
  "password": "string or null",
  "locked": false
}
```

### Permissions Tokens Collection

```json
{
  "_id": "UUID4",
  "userId": "UUID4",
  "createdAt": "datetime",
  "lastAccessed": "datetime",
  "permissions": {
    "role": "string"
  }
}
```

### Content Sessions Collection

```json
{
  "_id": "UUID4",
  "userId": "UUID4",
  "createdAt": "datetime",
  "lastAccessed": "datetime",
  "unreadMessages": false,
  "name": "string or null",
  "sessionData": {
    "storageKey": {
      "data_key": "data_value"
    }
  }
}
```

### Notifications Collection

```json
{
  "_id": "UUID4",
  "userId": "UUID4",
  "contentSessionId": "UUID4",
  "associatedMessageId": "UUID4",
  "associatedTaskId": "UUID4",
  "associatedImage": "string",
  "messageId": "UUID4",
  "createdAt": "datetime",
  "type": "string",
  "toastMessage": "string",
  "associatedMessage": "string",
  "urgency": "string",
  "persistent": boolean,
  "seen": boolean,
  "seenAt": "datetime or null",
  "responseData": {
    "data_key": "data_value"
  }
}
```

## Collection Indexes

### Permissions Tokens Collection Indexes

- `userId` (ASCENDING)

### Content Sessions Collection Indexes

- `userId` (ASCENDING)
- `contentSessionId` (ASCENDING)

### Notifications Collection Indexes

- `userId` (ASCENDING)
- `expiresAt` (ASCENDING) with TTL

### Users Collection Indexes

- `authProviders` (ASCENDING)
- `accessToken` (ASCENDING)

## Datetime Format

All datetime fields use ISO 8601 format with UTC timezone:

```python
datetime.now(timezone.utc).isoformat()
```

Example: `2024-06-14T19:12:39.676974+00:00`
