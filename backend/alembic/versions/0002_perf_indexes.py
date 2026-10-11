"""performance indexes (v2 refactor)

Why each index:
  * ix_videos_owner_status — list_for_owner WHERE deleted_at IS NULL is the
    library page's hot query. Composite covers owner + status + deleted.
  * ix_videos_status_updated_at — admin "failed videos" + worker scans.
  * ix_messages_conv_created — chat history retrieval is ORDER BY created_at.
  * ix_conversations_user_updated_at — conversation sidebar.
  * ix_chunks_video_idx already exists from v1.
"""
from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_videos_owner_status",
        "videos",
        ["owner_id", "status", "deleted_at"],
    )
    op.create_index(
        "ix_videos_status_updated_at",
        "videos",
        ["status", "updated_at"],
    )
    op.create_index(
        "ix_messages_conv_created",
        "messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_conversations_user_updated_at",
        "conversations",
        ["user_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_conversations_user_updated_at", table_name="conversations")
    op.drop_index("ix_messages_conv_created", table_name="messages")
    op.drop_index("ix_videos_status_updated_at", table_name="videos")
    op.drop_index("ix_videos_owner_status", table_name="videos")
