import { WebSocketMessage } from '../types';

type MessageHandler = (message: WebSocketMessage) => void;
type StatusHandler = (connected: boolean) => void;

export class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string = '';
  private messageHandlers: MessageHandler[] = [];
  private statusHandlers: StatusHandler[] = [];
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = false;
  private keepaliveInterval: ReturnType<typeof setInterval> | null = null;

  connect(sessionId: string): void {
    // In development, Vite runs on port 5173 but the backend WebSocket is on port 8000.
    // Use VITE_WS_URL env var or derive from VITE_API_URL, falling back to localhost:8000.
    let wsBase = import.meta.env.VITE_WS_URL;
    if (!wsBase) {
      const apiUrl = import.meta.env.VITE_API_URL;
      if (apiUrl) {
        // Derive WS URL from API URL (http://host:port/api -> ws://host:port)
        const baseUrl = apiUrl.replace(/\/api\/?$/, '').replace(/^http/, 'ws');
        wsBase = baseUrl;
      } else {
        // Default: backend runs on port 8000
        wsBase = `ws://${window.location.hostname}:8000`;
      }
    }
    this.url = `${wsBase}/ws/analysis/${sessionId}`;
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;
    this.createConnection();
  }

  /**
   * Returns a promise that resolves when the WebSocket connection is open,
   * or rejects if it fails to connect within the timeout.
   */
  waitForConnection(timeoutMs: number = 5000): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve();
        return;
      }

      const timeout = setTimeout(() => {
        cleanup();
        reject(new Error('WebSocket connection timeout'));
      }, timeoutMs);

      const cleanup = () => {
        clearTimeout(timeout);
        unsub();
      };

      const unsub = this.onStatusChange((connected) => {
        if (connected) {
          cleanup();
          resolve();
        }
      });
    });
  }

  private createConnection(): void {
    if (this.ws) {
      this.ws.close();
    }

    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.notifyStatus(true);
      this.startKeepalive();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.messageHandlers.forEach((handler) => handler(message));
      } catch {
        console.error('Failed to parse WebSocket message:', event.data);
      }
    };

    this.ws.onclose = () => {
      this.stopKeepalive();
      this.notifyStatus(false);
      if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // Error handler - close will fire next, triggering reconnect
    };
  }

  private scheduleReconnect(): void {
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    this.reconnectAttempts++;
    this.reconnectTimeout = setTimeout(() => {
      this.createConnection();
    }, delay);
  }

  private startKeepalive(): void {
    this.stopKeepalive();
    this.keepaliveInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 15000);
  }

  private stopKeepalive(): void {
    if (this.keepaliveInterval) {
      clearInterval(this.keepaliveInterval);
      this.keepaliveInterval = null;
    }
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.stopKeepalive();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.push(handler);
    return () => {
      this.messageHandlers = this.messageHandlers.filter((h) => h !== handler);
    };
  }

  onStatusChange(handler: StatusHandler): () => void {
    this.statusHandlers.push(handler);
    return () => {
      this.statusHandlers = this.statusHandlers.filter((h) => h !== handler);
    };
  }

  private notifyStatus(connected: boolean): void {
    this.statusHandlers.forEach((handler) => handler(connected));
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// Singleton instance
export const wsService = new WebSocketService();
