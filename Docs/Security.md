# Review Checklist

### Date: OCT 15, 2026

## Privacy and Data Handling
- Retention Policy & Data Lifecycle Schedules
- Privacy Policy & Transparency Disclosures
- Terms and Conditions
- Encryption (At-rest: AES-256; In-transit: TLS 1.3)
- Consent Management Platform (CMP) & Cookie Banner (Opt-in/Opt-out logic)
- "Do Not Sell or Share My Personal Info" / GPC (Global Privacy Control) support
- Data Subject Rights (DSAR, Deletion/Erasure, Rectification, Portability)
- Third-Party Vendor Data Processing Agreements (DPAs) & Cross-Border Transfers

## Access Control
- Identity & Access Governance:
  - Role-Based Access Control (RBAC) & Least Privilege enforcement
  - Multi-Factor Authentication (MFA) & Privileged Access Management (PAM)
- Infrastructure Access:
  - Filesystem ACLs & Permissions (POSIX / NTFS / Cloud Object Storage IAM policies)
  - Network ACLs & Security Groups (Ingress/Egress stateful and stateless traffic filters)

## Cache Safety & Edge Delivery
- Infrastructure & CDN Topology Mapping:
  - Reverse proxy layers, load balancers, CDN edge servers
- HTTP Cache Vulnerabilities (Layer 7):
  - Web Cache Deception (Path confusion, delimiter discrepancies, static extension stripping)
  - Web Cache Poisoning (Unkeyed headers, query parameters, fat GET requests, HTTP request smuggling)
  - Cache Directives Audit (`Cache-Control: no-store, private`, `Vary` headers, CDN Cache Deception Armor)
- DNS Security:
  - DNS cache poisoning & spoofing mitigations (DNSSEC verification, source port randomization)
- Emerging Attack Vectors:
  - CPDoS (Cache-Poisoned Denial of Service)
  - Hop-by-hop header abuses and parser discrepancies