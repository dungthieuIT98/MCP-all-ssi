package config

import (
	"fmt"
	"log"
	"os"
	"strconv"
	"strings"
	"time"
)

// TrinoConfig holds Trino connection parameters
type TrinoConfig struct {
	// Basic connection parameters
	Host              string
	Port              int
	User              string
	Password          string
	Catalog           string
	Schema            string
	Scheme            string
	SSL               bool
	SSLInsecure       bool
	AllowWriteQueries bool          // Controls whether non-read-only SQL queries are allowed
	QueryTimeout      time.Duration // Query execution timeout
	MaxRows           int           // Maximum number of rows returned per query (0 = unlimited)

	// Allowlist configuration for filtering catalogs, schemas, and tables
	AllowedCatalogs []string // List of allowed catalogs (empty means no filtering)
	AllowedSchemas  []string // List of allowed schemas in catalog.schema format
	AllowedTables   []string // List of allowed tables in catalog.schema.table format

	// Impersonation configuration
	// EnableImpersonation trusts the X-User-Email header on incoming HTTP requests
	// to determine the Trino principal. This header MUST be set (and stripped from
	// client input) by a trusted upstream gateway (e.g. Kong) that has already
	// authenticated the caller — mcp-trino does not verify it itself.
	EnableImpersonation bool // Enable Trino user impersonation via X-User-Email → X-Trino-User

	// Query attribution
	TrinoSource string // Value for X-Trino-Source header (identifies query source to Trino)

	// Query result cache
	QueryCacheTTL time.Duration // TTL for read-only query result cache (0 = disabled)

	// Preview and pagination
	MaxPreviewRows    int // Maximum rows to return inline (excess written to temp file, default 20)
}

// NewTrinoConfig creates a new TrinoConfig with values from environment variables or defaults
func NewTrinoConfig() (*TrinoConfig, error) {
	return NewTrinoConfigWithVersion("dev")
}

// NewTrinoConfigWithVersion creates a new TrinoConfig with a specific version for X-Trino-Source
func NewTrinoConfigWithVersion(version string) (*TrinoConfig, error) {
	resolveEnv := getEnv

	port, _ := strconv.Atoi(resolveEnv("TRINO_PORT", "8080"))
	ssl, _ := strconv.ParseBool(resolveEnv("TRINO_SSL", "true"))
	sslInsecure, _ := strconv.ParseBool(resolveEnv("TRINO_SSL_INSECURE", "true"))
	scheme := resolveEnv("TRINO_SCHEME", "https")
	allowWriteQueries, _ := strconv.ParseBool(resolveEnv("TRINO_ALLOW_WRITE_QUERIES", "false"))

	// Parse max rows from environment variable
	const defaultMaxRows = 10000
	maxRowsStr := resolveEnv("TRINO_MAX_ROWS", strconv.Itoa(defaultMaxRows))
	maxRows, err := strconv.Atoi(maxRowsStr)
	switch {
	case err != nil:
		log.Printf("WARNING: Invalid TRINO_MAX_ROWS '%s': not an integer. Using default of %d", maxRowsStr, defaultMaxRows)
		maxRows = defaultMaxRows
	case maxRows < 0:
		log.Printf("WARNING: Invalid TRINO_MAX_ROWS '%d': must be non-negative. Using default of %d", maxRows, defaultMaxRows)
		maxRows = defaultMaxRows
	}

	// Parse query timeout from environment variable
	const defaultTimeout = 300
	timeoutStr := resolveEnv("TRINO_QUERY_TIMEOUT", strconv.Itoa(defaultTimeout))
	timeoutInt, err := strconv.Atoi(timeoutStr)

	// Validate timeout value
	switch {
	case err != nil:
		log.Printf("WARNING: Invalid TRINO_QUERY_TIMEOUT '%s': not an integer. Using default of %d seconds", timeoutStr, defaultTimeout)
		timeoutInt = defaultTimeout
	case timeoutInt <= 0:
		log.Printf("WARNING: Invalid TRINO_QUERY_TIMEOUT '%d': must be positive. Using default of %d seconds", timeoutInt, defaultTimeout)
		timeoutInt = defaultTimeout
	}

	queryTimeout := time.Duration(timeoutInt) * time.Second

	// Parse allowlist configuration
	allowedCatalogs := parseAllowlist(resolveEnv("TRINO_ALLOWED_CATALOGS", ""))
	allowedSchemas := parseAllowlist(resolveEnv("TRINO_ALLOWED_SCHEMAS", ""))
	allowedTables := parseAllowlist(resolveEnv("TRINO_ALLOWED_TABLES", ""))

	// Parse impersonation configuration
	enableImpersonation, _ := strconv.ParseBool(resolveEnv("TRINO_ENABLE_IMPERSONATION", "false"))

	// Parse Trino source configuration with default
	trinoSource := resolveEnv("TRINO_SOURCE", fmt.Sprintf("mcp-trino/%s", version))
	if trinoSource == "" {
		// If explicitly set to empty, use default
		trinoSource = fmt.Sprintf("mcp-trino/%s", version)
	}

	// Validate allowlist formats
	if err := validateAllowlist("TRINO_ALLOWED_SCHEMAS", allowedSchemas, 1); err != nil { // Must have catalog.schema format
		return nil, err
	}
	if err := validateAllowlist("TRINO_ALLOWED_TABLES", allowedTables, 2); err != nil { // Must have catalog.schema.table format
		return nil, err
	}

	// If using HTTPS, force SSL to true
	if strings.EqualFold(scheme, "https") {
		ssl = true
	}

	// Log a warning if write queries are allowed
	if allowWriteQueries {
		log.Println("WARNING: Write queries are enabled (TRINO_ALLOW_WRITE_QUERIES=true). SQL injection protection is bypassed.")
	}

	// Log allowlist configuration
	logAllowlistConfiguration(allowedCatalogs, allowedSchemas, allowedTables)

	// Log impersonation configuration
	if enableImpersonation {
		log.Printf("INFO: Trino user impersonation enabled (TRINO_ENABLE_IMPERSONATION=true)")
		log.Println("INFO: Principal is read from the X-User-Email request header")
		log.Println("WARNING: X-User-Email is trusted as-is. It MUST be set (and stripped from client input) by a trusted upstream gateway that has already authenticated the caller.")
	} else {
		log.Println("INFO: Trino user impersonation disabled (TRINO_ENABLE_IMPERSONATION=false)")
	}

	// Log max rows configuration
	if maxRows > 0 {
		log.Printf("INFO: Max rows per query: %d (TRINO_MAX_ROWS)", maxRows)
	} else {
		log.Println("WARNING: No row limit configured (TRINO_MAX_ROWS=0). Large queries may cause high memory usage.")
	}

	// Log query attribution configuration
	log.Printf("INFO: Trino query source attribution: %s", trinoSource)

	// Parse query cache TTL (0 = disabled by default)
	cacheTTLStr := resolveEnv("TRINO_QUERY_CACHE_TTL", "0")
	cacheTTLInt, err := strconv.Atoi(cacheTTLStr)
	switch {
	case err != nil:
		log.Printf("WARNING: Invalid TRINO_QUERY_CACHE_TTL '%s': not an integer. Cache disabled.", cacheTTLStr)
		cacheTTLInt = 0
	case cacheTTLInt < 0:
		log.Printf("WARNING: Invalid TRINO_QUERY_CACHE_TTL '%d': must be non-negative. Cache disabled.", cacheTTLInt)
		cacheTTLInt = 0
	case cacheTTLInt > 0:
		log.Printf("INFO: Query result cache enabled with TTL=%ds (TRINO_QUERY_CACHE_TTL)", cacheTTLInt)
	}
	queryCacheTTL := time.Duration(cacheTTLInt) * time.Second

	// Parse max preview rows from environment variable
	const defaultMaxPreviewRows = 20
	maxPreviewRowsStr := resolveEnv("TRINO_MAX_PREVIEW_ROWS", strconv.Itoa(defaultMaxPreviewRows))
	maxPreviewRows, err := strconv.Atoi(maxPreviewRowsStr)
	switch {
	case err != nil:
		log.Printf("WARNING: Invalid TRINO_MAX_PREVIEW_ROWS '%s': not an integer. Using default of %d", maxPreviewRowsStr, defaultMaxPreviewRows)
		maxPreviewRows = defaultMaxPreviewRows
	case maxPreviewRows < 0:
		log.Printf("WARNING: Invalid TRINO_MAX_PREVIEW_ROWS '%d': must be non-negative. Using default of %d", maxPreviewRows, defaultMaxPreviewRows)
		maxPreviewRows = defaultMaxPreviewRows
	}

	return &TrinoConfig{
		Host:                resolveEnv("TRINO_HOST", "localhost"),
		Port:                port,
		User:                resolveEnv("TRINO_USER", "trino"),
		Password:            resolveEnv("TRINO_PASSWORD", ""),
		Catalog:             resolveEnv("TRINO_CATALOG", "memory"),
		Schema:              resolveEnv("TRINO_SCHEMA", "default"),
		Scheme:              scheme,
		SSL:                 ssl,
		SSLInsecure:         sslInsecure,
		AllowWriteQueries:   allowWriteQueries,
		QueryTimeout:        queryTimeout,
		MaxRows:             maxRows,
		AllowedCatalogs:     allowedCatalogs,
		AllowedSchemas:      allowedSchemas,
		AllowedTables:       allowedTables,
		EnableImpersonation: enableImpersonation,
		TrinoSource:         trinoSource,
		QueryCacheTTL:       queryCacheTTL,
		MaxPreviewRows:      maxPreviewRows,
	}, nil
}

// parseAllowlist parses a comma-separated allowlist from an environment variable
func parseAllowlist(value string) []string {
	if value == "" {
		return nil
	}

	// Split by comma and clean up entries
	items := strings.Split(value, ",")
	var result []string
	for _, item := range items {
		cleaned := strings.TrimSpace(item)
		if cleaned != "" {
			result = append(result, cleaned)
		}
	}
	return result
}

// validateAllowlist validates the format of allowlist entries
func validateAllowlist(envVar string, allowlist []string, expectedDots int) error {
	for _, item := range allowlist {
		dots := strings.Count(item, ".")
		if dots != expectedDots {
			return fmt.Errorf("invalid format in %s: '%s' (expected %d dots, found %d)",
				envVar, item, expectedDots, dots)
		}
	}
	return nil
}

// logAllowlistConfiguration logs the current allowlist configuration
func logAllowlistConfiguration(catalogs, schemas, tables []string) {
	if len(catalogs) > 0 || len(schemas) > 0 || len(tables) > 0 {
		log.Println("INFO: Trino allowlist configuration:")
		if len(catalogs) > 0 {
			log.Printf("  - Allowed catalogs: %s (%d configured)", strings.Join(catalogs, ", "), len(catalogs))
		}
		if len(schemas) > 0 {
			log.Printf("  - Allowed schemas: %s (%d configured)", strings.Join(schemas, ", "), len(schemas))
		}
		if len(tables) > 0 {
			log.Printf("  - Allowed tables: %s (%d configured)", strings.Join(tables, ", "), len(tables))
		}
	} else {
		log.Println("INFO: No Trino allowlists configured - all catalogs, schemas, and tables are accessible")
	}
}

// getEnv retrieves an environment variable or returns a default value
func getEnv(key, fallback string) string {
	if value, exists := os.LookupEnv(key); exists {
		return value
	}
	return fallback
}
