package mcp

import (
	"net/http"
	"testing"
)

func TestValidateUserEmail(t *testing.T) {
	tests := []struct {
		name       string
		header     string
		setHeader  bool
		wantEmail  string
		wantReject bool
	}{
		{name: "valid ssi.com.vn", header: "demoA@ssi.com.vn", setHeader: true, wantEmail: "demoA@ssi.com.vn"},
		{name: "valid bare ssi", header: "admin@ssi", setHeader: true, wantEmail: "admin@ssi"},
		{name: "valid ssi.vn", header: "user@ssi.vn", setHeader: true, wantEmail: "user@ssi.vn"},
		{name: "valid with surrounding spaces", header: "  demoA@ssi.com.vn  ", setHeader: true, wantEmail: "demoA@ssi.com.vn"},
		{name: "valid uppercase domain", header: "user@SSI.COM.VN", setHeader: true, wantEmail: "user@SSI.COM.VN"},
		{name: "missing header", setHeader: false, wantReject: true},
		{name: "empty header", header: "", setHeader: true, wantReject: true},
		{name: "whitespace only", header: "   ", setHeader: true, wantReject: true},
		{name: "no at sign", header: "demoA", setHeader: true, wantReject: true},
		{name: "trailing at sign", header: "demoA@", setHeader: true, wantReject: true},
		{name: "foreign domain", header: "attacker@gmail.com", setHeader: true, wantReject: true},
		{name: "lookalike domain ssix", header: "attacker@ssix.com", setHeader: true, wantReject: true},
		{name: "domain containing ssi not prefix", header: "user@notssi.com", setHeader: true, wantReject: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			r, _ := http.NewRequest(http.MethodPost, "/mcp", nil)
			if tt.setHeader {
				r.Header.Set(userEmailHeader, tt.header)
			}

			email, reason := validateUserEmail(r)

			if tt.wantReject {
				if reason == "" {
					t.Errorf("expected rejection for %q, got accepted (email=%q)", tt.header, email)
				}
				if email != "" {
					t.Errorf("expected empty email on rejection, got %q", email)
				}
				return
			}

			if reason != "" {
				t.Errorf("expected %q to be accepted, got rejected: %s", tt.header, reason)
			}
			if email != tt.wantEmail {
				t.Errorf("expected email %q, got %q", tt.wantEmail, email)
			}
		})
	}
}
