"""One-shot migration from single-user to multi-user setup.

Runs on gateway startup when the users database is empty.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from loguru import logger


async def migrate_existing_to_multi_user(
    user_store: Any,
    config: Any,
    workspace: Path,
    session_manager: Any | None = None,
) -> dict[str, Any]:
    """Run one-shot migration when upgrading from single-user to multi-user.

    Steps:
    1. Create the super_admin from config (already done by UserStore.initialize)
    2. Copy existing memory files to the super_admin's user workspace
    3. Link all approved pairing senders to the super_admin
    4. Report what was migrated

    Returns a summary dict of actions taken.
    """
    summary: dict[str, Any] = {
        "super_admin_created": False,
        "memory_files_migrated": 0,
        "pairings_linked": 0,
        "sessions_available": 0,
        "notes": [],
    }

    # 1. Ensure user DB is initialized (creates super_admin if empty)
    await user_store.initialize(config)
    users = await user_store.list_users()
    super_admin = next((u for u in users if u.get("role") == "super_admin"), None)

    if super_admin is None:
        logger.warning("No super_admin found after initialization — skipping migration")
        return summary

    super_admin_id = super_admin["id"]
    summary["super_admin_created"] = True
    summary["super_admin_username"] = super_admin.get("username")

    # 2. Copy existing memory files to super_admin's workspace
    user_workspace = workspace / "workspaces" / super_admin_id
    user_workspace.mkdir(parents=True, exist_ok=True)

    memory_files = [
        "SOUL.md",
        "USER.md",
        "AGENTS.md",
    ]
    memory_dir_src = workspace / "memory"
    memory_dir_dst = user_workspace / "memory"
    memory_dir_dst.mkdir(parents=True, exist_ok=True)

    for name in memory_files:
        src = workspace / name
        dst = user_workspace / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            summary["memory_files_migrated"] += 1
            logger.info("migrated memory file: {} -> {}", src, dst)

    # Copy memory directory contents
    for src_path in memory_dir_src.glob("*"):
        if src_path.is_file():
            dst_path = memory_dir_dst / src_path.name
            if not dst_path.exists():
                shutil.copy2(src_path, dst_path)
                summary["memory_files_migrated"] += 1

    # 3. Link approved pairing senders
    try:
        from nanobot.pairing.store import get_approved
        # Known channel names that might have approved senders
        known_channels = [
            "telegram", "discord", "slack", "whatsapp", "matrix",
            "wecom", "weixin", "feishu", "dingtalk", "qq",
            "napcat", "email", "msteams", "signal", "mattermost", "mochat",
        ]
        for channel_name in known_channels:
            approved_senders = get_approved(channel_name)
            for sender_id in approved_senders:
                ok = await user_store.link_identity(
                    super_admin_id, channel_name, str(sender_id)
                )
                if ok:
                    summary["pairings_linked"] += 1
                    logger.info(
                        "linked pairing {}:{} -> user {}",
                        channel_name,
                        sender_id,
                        super_admin_id,
                    )
    except Exception as e:
        summary["notes"].append(f"pairing migration skipped: {e}")
        logger.debug("pairing migration error: {}", e)

    # 4. Count existing sessions
    if session_manager is not None:
        try:
            sessions = session_manager.list_sessions()
            summary["sessions_available"] = len(sessions)
        except Exception:
            pass

    if summary["memory_files_migrated"] > 0:
        summary["notes"].append(
            f"Migrated {summary['memory_files_migrated']} memory files "
            f"to super_admin workspace"
        )
    if summary["pairings_linked"] > 0:
        summary["notes"].append(
            f"Linked {summary['pairings_linked']} approved channel senders "
            f"to super_admin"
        )

    logger.info(
        "multi-user migration complete: admin={}, files={}, pairings={}, sessions={}",
        super_admin.get("username"),
        summary["memory_files_migrated"],
        summary["pairings_linked"],
        summary["sessions_available"],
    )
    return summary
