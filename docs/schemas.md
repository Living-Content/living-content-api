# Data Schemas

## Redis Schemas

### User

```json
{
  "user:UUID4" {
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
  "accessToken:UUID4" {
    "userId": "UUID4",
    "createdAt": "datetime"
  }
}
```

## MongoDB Schemas

### Users

```json
{
  "_id": "UUID4",
  "createdAt": "datetime",
  "lastAccessed": "datetime",
  "accessToken": "UUID4 or null",
  "permissionsToken": "UUID4",
  "requests": {
    "allTime": 0
  },
  "verified": false,
  "emailAddress": "string or null",
  "password": "string or null",
  "locked": false
}
```

### Access Tokens

```json
{
  "_id": "UUID4",
  "userId": "UUID4",
  "createdAt": "datetime"
}
```

### Permissions Tokens

```json
{
  "_id": "UUID4 (userId)",
  "userId": "UUID4",
  "createdAt": "datetime",
  "permissions": {
    [
      "role": "string",
      "permission_key": "permission_value",
      "..."
    ]
    "..."
  }
}
```

### Content Sessions

```json
{
  "_id": "UUID4",
  "userId": "UUID4",
  "name": null,
  "createdAt": "datetime",
  "lastAccessed": "datetime",
  "sessionData": {
    {
      "storageKey": {
        "data_keys": "data_values"
      }
    }
  }
}
```

### Notifications

```json
{
  "_id": "UUID4",
  "userId": "UUID4",
  "createdAt": "datetime",
  "contentSessionId": "UUID4",
  "context": "text",
  "message": "A new message has been received.",
  "urgency": "low",
  "data": { 
    "key": "value",
    "..."
  }
}
```

## Datetime Format

All datetime fields use: `datetime.now(timezone.utc).isoformat()`  
Example: `2024-06-14T19:12:39.676974+00:00`
