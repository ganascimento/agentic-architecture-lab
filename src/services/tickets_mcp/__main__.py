from src.services.tickets_mcp.server import serve

try:
    serve()
except KeyboardInterrupt:  # Ctrl+C in the host's terminal reaches its child processes too: exit quietly
    pass
