"""OCI Ampere A1 free-tier instance requester.

Polls the OCI LaunchInstance API in a loop until an ARM slot opens, then
notifies a Discord webhook with the instance details.

Setup:
    1. pip install -r requirements.txt
    2. Copy .env.example -> .env and fill in values
    3. Ensure ~/.oci/config is configured (run `oci setup config`)
    4. python request_oci.py

The script runs until the instance is created or a non-capacity error occurs.
Run it inside a tmux/screen session or as a systemd service for reliability.
"""

import os
import time
from datetime import datetime, timezone

import oci
import requests
from dotenv import load_dotenv

load_dotenv()

# --- config from .env ---
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DISCORD_MENTION = os.environ.get("DISCORD_MENTION", "")       # e.g. <@123456789>

COMPARTMENT_ID       = os.environ["OCI_COMPARTMENT_ID"]
AVAILABILITY_DOMAIN  = os.environ["OCI_AVAILABILITY_DOMAIN"]  # e.g. "abcd:US-ASHBURN-AD-1"
SUBNET_ID            = os.environ["OCI_SUBNET_ID"]
IMAGE_ID             = os.environ["OCI_IMAGE_ID"]              # Ubuntu 22.04 ARM image OCID
SSH_PUBLIC_KEY       = os.environ["OCI_SSH_PUBLIC_KEY"]        # full key string (ssh-ed25519 ...)

SHAPE       = os.environ.get("OCI_SHAPE", "VM.Standard.A1.Flex")
OCPU_COUNT  = float(os.environ.get("OCI_OCPU_COUNT", "4"))
MEMORY_GB   = float(os.environ.get("OCI_MEMORY_GB", "24"))
RETRY_INTERVAL_SEC = int(os.environ.get("RETRY_INTERVAL_SEC", "60"))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def send_discord(title: str, description: str, success: bool, mention: bool = False) -> None:
    if not DISCORD_WEBHOOK_URL:
        return
    color = 0x57F287 if success else 0xED4245
    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    }
    if mention and DISCORD_MENTION:
        payload["content"] = DISCORD_MENTION
        payload["allowed_mentions"] = {"parse": ["users", "roles"]}
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if r.status_code >= 300:
            print(f"[discord] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[discord] notify failed: {e}")


def try_launch(compute: oci.core.ComputeClient) -> oci.core.models.Instance:
    details = oci.core.models.LaunchInstanceDetails(
        compartment_id=COMPARTMENT_ID,
        display_name=f"arm-{int(time.time())}",
        availability_domain=AVAILABILITY_DOMAIN,
        shape=SHAPE,
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=OCPU_COUNT,
            memory_in_gbs=MEMORY_GB,
        ),
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            image_id=IMAGE_ID,
            source_type="image",
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=SUBNET_ID,
            assign_public_ip=True,
        ),
        metadata={"ssh_authorized_keys": SSH_PUBLIC_KEY},
    )
    return compute.launch_instance(details).data


def main() -> None:
    config = oci.config.from_file()
    compute = oci.core.ComputeClient(config)

    print(f"[{_now()}] Starting OCI ARM requester — shape={SHAPE} ocpu={OCPU_COUNT} mem={MEMORY_GB}GB")
    print(f"[{_now()}] Polling every {RETRY_INTERVAL_SEC}s until a slot opens...")

    send_discord(
        "🔄 OCI ARM requester started",
        f"Shape: `{SHAPE}` · {OCPU_COUNT} OCPU · {MEMORY_GB} GB\nPolling every {RETRY_INTERVAL_SEC}s",
        success=True,
        mention=False,
    )

    attempt = 0
    while True:
        attempt += 1
        try:
            instance = try_launch(compute)
            print(f"[{_now()}] ✅ SUCCESS on attempt #{attempt} — {instance.id}")
            send_discord(
                "✅ OCI ARM instance created!",
                (
                    f"**Instance ID:** `{instance.id}`\n"
                    f"**Name:** {instance.display_name}\n"
                    f"**Shape:** {instance.shape}\n"
                    f"**AD:** {instance.availability_domain}\n"
                    f"**Attempt:** #{attempt}\n\n"
                    f"Check OCI Console for the public IP once it reaches RUNNING state."
                ),
                success=True,
                mention=True,
            )
            return

        except oci.exceptions.ServiceError as e:
            msg_lower = (e.message or "").lower()
            is_capacity = (
                e.status == 429  # rate limited — always retry
                or (e.status == 500 and any(
                    kw in msg_lower for kw in ("out of capacity", "out of host capacity")
                ))
            )
            if is_capacity:
                print(f"[{_now()}] Attempt #{attempt}: out of capacity — retrying in {RETRY_INTERVAL_SEC}s")
            else:
                msg = f"status={e.status} code={e.code}: {e.message}"
                print(f"[{_now()}] Attempt #{attempt}: unexpected error — {msg}")
                send_discord(
                    "❌ OCI requester hit a fatal error",
                    f"Attempt #{attempt}\n```{msg}```",
                    success=False,
                    mention=True,
                )
                raise

        time.sleep(RETRY_INTERVAL_SEC)


if __name__ == "__main__":
    main()
