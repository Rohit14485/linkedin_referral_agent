"""
Web UI Launcher for ReferralAI Studio.
"""

import argparse
import sys
import uvicorn
from rich.console import Console
from rich.panel import Panel

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Launch ReferralAI Studio Web UI")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host IP to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code change")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    console.print(Panel.fit(
        f"[bold white]ReferralAI Studio - Web Dashboard & Monitor[/bold white]\n\n"
        f"Server running at: [bold green underline]{url}[/bold green underline]\n"
        f"Real-time Live Monitoring: [cyan]Active (SSE Stream)[/cyan]\n"
        f"Press [bold red]Ctrl+C[/bold red] to stop the server.",
        title="Web Interface Ready",
        border_style="green"
    ))

    uvicorn.run(
        "linkedin_referral_agent.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
