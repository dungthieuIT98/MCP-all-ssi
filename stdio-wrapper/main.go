package main

import (
	"bufio"
	"bytes"
	"fmt"
	"io"
	"net/http"
	"os"
)

const upstreamURL = "http://localhost:6275/mcp"

func main() {
	client := &http.Client{}
	reader := bufio.NewReader(os.Stdin)

	for {
		line, err := reader.ReadBytes('\n')
		if err != nil {
			if err == io.EOF {
				return
			}
			fmt.Fprintf(os.Stderr, "[stdio-wrapper] read error: %v\n", err)
			return
		}

		line = bytes.TrimSpace(line)
		if len(line) == 0 {
			continue
		}

		req, err := http.NewRequest("POST", upstreamURL, bytes.NewReader(line))
		if err != nil {
			fmt.Fprintf(os.Stderr, "[stdio-wrapper] request error: %v\n", err)
			continue
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err := client.Do(req)
		if err != nil {
			fmt.Fprintf(os.Stderr, "[stdio-wrapper] upstream error: %v\n", err)
			continue
		}

		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			fmt.Fprintf(os.Stderr, "[stdio-wrapper] read body error: %v\n", err)
			continue
		}

		// MCP over stdio: each message is a line
		fmt.Fprintf(os.Stdout, "%s\n", bytes.TrimSpace(body))
	}
}
