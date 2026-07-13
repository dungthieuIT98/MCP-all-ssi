package mcp

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	mcpserver "github.com/mark3labs/mcp-go/server"
	"gitlab.ssi.com.vn/dto-data/mcp_server_trino/internal/config"
	"gitlab.ssi.com.vn/dto-data/mcp_server_trino/internal/trino"
)

// userEmailHeader is the HTTP header a trusted upstream gateway (e.g. Kong) sets
// after authenticating the caller. mcp-trino trusts it as-is and does not
// verify it — the gateway MUST strip any client-supplied value for this header.
const userEmailHeader = "X-User-Email"

// Server represents the MCP server with all components
type Server struct {
	mcpServer *mcpserver.MCPServer
	config    *config.TrinoConfig
	version   string
}

// NewServer creates a new MCP server instance with all components
func NewServer(trinoClient *trino.Client, trinoConfig *config.TrinoConfig, version string) *Server {
	mcpServer := createMCPServer(trinoClient, trinoConfig, version)

	return &Server{
		mcpServer: mcpServer,
		config:    trinoConfig,
		version:   version,
	}
}

func createMCPServer(trinoClient *trino.Client, trinoConfig *config.TrinoConfig, version string) *mcpserver.MCPServer {
	options := []mcpserver.ServerOption{mcpserver.WithToolCapabilities(true)}

	mcpServer := mcpserver.NewMCPServer("Trino MCP Server", version, options...)

	trinoHandlers := NewTrinoHandlers(trinoClient, trinoConfig)
	RegisterTrinoTools(mcpServer, trinoHandlers)

	return mcpServer
}

// userEmailContextFunc extracts the X-User-Email header set by the trusted
// upstream gateway and stores it in context for impersonation.
func userEmailContextFunc(ctx context.Context, r *http.Request) context.Context {
	email := r.Header.Get(userEmailHeader)
	if email == "" {
		return ctx
	}
	return trino.WithUserEmail(ctx, email)
}

// ServeStdio starts the MCP server with STDIO transport
func (s *Server) ServeStdio() error {
	return mcpserver.ServeStdio(s.mcpServer)
}

// ServeHTTP starts the MCP server with HTTP transport
func (s *Server) ServeHTTP(port string) error {
	addr := fmt.Sprintf(":%s", port)

	log.Println("Setting up StreamableHTTP server...")

	streamableServer := mcpserver.NewStreamableHTTPServer(
		s.mcpServer,
		mcpserver.WithEndpointPath("/mcp"),
		mcpserver.WithHTTPContextFunc(userEmailContextFunc),
		mcpserver.WithStateLess(false),
	)

	mux := http.NewServeMux()
	mux.HandleFunc("/status", s.handleStatus)

	mcpHandler := s.createMCPHandler(streamableServer)
	mux.HandleFunc("/mcp", mcpHandler)
	mux.HandleFunc("/sse", mcpHandler)

	httpServer := &http.Server{Addr: addr, Handler: mux}

	done := make(chan bool, 1)
	go s.handleSignals(done)

	go func() {
		certFile := getEnv("HTTPS_CERT_FILE", "")
		keyFile := getEnv("HTTPS_KEY_FILE", "")

		mcpHost := getEnv("MCP_HOST", "localhost")
		mcpPort := getEnv("MCP_PORT", "8080")
		scheme := s.getScheme()
		mcpURL := getEnv("MCP_URL", fmt.Sprintf("%s://%s:%s", scheme, mcpHost, mcpPort))

		impersonationStatus := s.getImpersonationStatus()

		if certFile != "" && keyFile != "" {
			log.Printf("Starting HTTPS server on %s%s", addr, impersonationStatus)
			log.Printf("  - Modern endpoint: %s/mcp", mcpURL)
			log.Printf("  - Legacy endpoint: %s/sse (backward compatibility)", mcpURL)

			if err := httpServer.ListenAndServeTLS(certFile, keyFile); err != nil && err != http.ErrServerClosed {
				log.Fatalf("HTTPS server error: %v", err)
			}
		} else {
			log.Printf("Starting HTTP server on %s%s", addr, impersonationStatus)
			log.Printf("  - Modern endpoint: %s/mcp", mcpURL)
			log.Printf("  - Legacy endpoint: %s/sse (backward compatibility)", mcpURL)

			if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
				log.Fatalf("HTTP server error: %v", err)
			}
		}
	}()

	<-done
	log.Println("Shutting down HTTP server...")

	// Allow 30 seconds for graceful shutdown
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	log.Println("Waiting for active connections to finish (max 30 seconds)...")
	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("HTTP server forced shutdown after timeout: %v", err)
		return httpServer.Close()
	}
	log.Println("HTTP server shutdown completed gracefully")
	return nil
}

// createMCPHandler creates the shared MCP handler function
func (s *Server) createMCPHandler(streamableServer *mcpserver.StreamableHTTPServer) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK)
			return
		}

		log.Printf("MCP %s %s from %s", r.Method, r.URL.Path, r.RemoteAddr)

		streamableServer.ServeHTTP(w, r)
	}
}

// handleStatus handles the status endpoint
func (s *Server) handleStatus(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = fmt.Fprintf(w, `{"status":"ok","version":"%s"}`, s.version)
}

// handleSignals handles graceful shutdown signals
func (s *Server) handleSignals(done chan<- bool) {
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGINT, syscall.SIGTERM)
	<-ch
	done <- true
}

func (s *Server) getScheme() string {
	certFile := getEnv("HTTPS_CERT_FILE", "")
	keyFile := getEnv("HTTPS_KEY_FILE", "")

	if certFile != "" && keyFile != "" {
		return "https"
	}
	return "http"
}

// getImpersonationStatus returns impersonation status for startup logging
func (s *Server) getImpersonationStatus() string {
	if s.config.EnableImpersonation {
		return " (impersonation enabled via X-User-Email — must be set by a trusted upstream gateway)"
	}
	return " (impersonation disabled)"
}

// getEnv gets environment variable with default value
func getEnv(key, def string) string {
	if v, ok := os.LookupEnv(key); ok {
		return v
	}
	return def
}
