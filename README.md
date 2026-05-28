# OCI ARM Requester

Polls the Oracle Cloud Infrastructure (OCI) API until an **Ampere A1 free-tier** ARM slot opens, then notifies you via Discord.

OCI Always-Free ARM instances are almost always "out of capacity." This script retries automatically every 60 seconds until one becomes available, then pings you the moment it's provisioned.

## How it works

1. Calls OCI `LaunchInstance` API in a loop
2. Silently retries on "out of capacity" errors
3. Sends a Discord notification (with mention) when the instance is created
4. Sends a Discord notification (with mention) if a fatal error occurs

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure OCI SDK

```bash
oci setup config
```

Follow the prompts. This creates `~/.oci/config` with your tenancy/user OCIDs and key.

### 3. Create your `.env`

```bash
cp .env.example .env
```

Fill in the values — see `.env.example` for where to find each one in OCI Console.

| Variable | Description |
|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Webhook URL from your Discord server settings |
| `DISCORD_MENTION` | Your user/role mention string e.g. `<@123456789>` (optional) |
| `OCI_COMPARTMENT_ID` | OCID of the compartment to create the instance in |
| `OCI_AVAILABILITY_DOMAIN` | e.g. `abcd:AP-SINGAPORE-1-AD-1` |
| `OCI_SUBNET_ID` | OCID of the subnet for the instance NIC |
| `OCI_IMAGE_ID` | OCID of Ubuntu 22.04 Minimal (aarch64) platform image |
| `OCI_SSH_PUBLIC_KEY` | Full public key string (contents of `~/.ssh/id_ed25519.pub`) |
| `OCI_OCPU_COUNT` | Number of OCPUs (max 4 for free tier, default `4`) |
| `OCI_MEMORY_GB` | RAM in GB (max 24 for free tier, default `24`) |
| `RETRY_INTERVAL_SEC` | Seconds between retries (default `60`, min `30`) |

### 4. Run

```bash
python request_oci.py
```

Run it inside `tmux` or `screen` so it keeps going if your terminal closes:

```bash
tmux new -s oci
python request_oci.py
# Ctrl+B then D to detach
```

## Discord notifications

| Event | Ping? |
|-------|-------|
| 🔄 Script started | No |
| ✅ Instance created | **Yes** — includes instance ID and next steps |
| ❌ Fatal error | **Yes** |

## Finding OCI values

- **Compartment ID** — OCI Console → Identity & Security → Compartments → copy OCID
- **Availability Domain** — OCI Console → Compute → Instances → Create Instance → Availability Domain dropdown
- **Subnet ID** — OCI Console → Networking → Virtual Cloud Networks → your VCN → Subnets → copy OCID
- **Image ID** — OCI Console → Compute → Images → Platform Images → filter `aarch64` → Ubuntu 22.04 Minimal → copy OCID
