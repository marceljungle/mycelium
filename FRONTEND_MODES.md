# Frontend Mode Configuration

Mycelium supports two frontend modes:

## Server Mode (Default)
- **URL**: Main server (usually port 8000)
- **Interface**: Full Mycelium interface with search, library management, and settings
- **Build command**: `./build_frontend.sh` (or just the first part)
- **Environment**: No special environment variables needed

## Client Mode
- **URL**: Client server (usually port 3001)  
- **Interface**: Simplified client configuration interface for GPU workers
- **Build command**: `./build_client_frontend.sh`
- **Environment**: `NEXT_PUBLIC_MYCELIUM_MODE=client`

## Building Both Modes

To build both frontend modes for distribution:

```bash
# Builds both server and client frontends
./build_frontend.sh
```

This will create:
- `src/mycelium/frontend_dist/` - Server frontend files
- `src/mycelium/client_frontend_dist/` - Client frontend files

## Frontend Mode Detection

The frontend automatically detects which mode to display based on the `NEXT_PUBLIC_MYCELIUM_MODE` environment variable:

```typescript
// In src/config/api.ts
const isClientMode = (): boolean => {
  return process.env.NEXT_PUBLIC_MYCELIUM_MODE === 'client';
};

// In src/app/page.tsx
if (IS_CLIENT_MODE) {
  return <ClientPage />;  // Show client configuration interface
}
// Otherwise show full server interface
```

## API Endpoints

### Server Mode
- Root: `/` → Full Mycelium interface
- API docs: `/api` → API documentation

### Client Mode  
- Root: `/` → Client configuration interface
- Config: `/api/config` → Client configuration endpoints

## Validation

Use the validation script to verify builds:

```bash
python3 validate_frontend_routing.py
```

This checks:
- Both frontend builds exist
- Correct content in each build
- Proper API endpoint configuration
- Static asset directories are present