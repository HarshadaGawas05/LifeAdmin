"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-10-07 00:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('recurring_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('merchant', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('interval_days', sa.Integer(), nullable=False),
        sa.Column('last_paid_date', sa.DateTime(), nullable=False),
        sa.Column('next_due_date', sa.DateTime(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('source_transparency', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recurring_subscriptions_id'), 'recurring_subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_recurring_subscriptions_merchant'), 'recurring_subscriptions', ['merchant'], unique=False)

    op.create_table('tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('priority_score', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('source_details', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), nullable=True),
        sa.Column('interval_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_id'), 'tasks', ['id'], unique=False)
    op.create_index(op.f('ix_tasks_name'), 'tasks', ['name'], unique=False)

    op.create_table('gmail_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('encrypted_token', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_gmail_tokens_id'), 'gmail_tokens', ['id'], unique=False)
    op.create_index(op.f('ix_gmail_tokens_user_id'), 'gmail_tokens', ['user_id'], unique=False)

    op.create_table('oauth_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('email_address', sa.String(length=255), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=False),
        sa.Column('token_expiry', sa.DateTime(), nullable=True),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('needs_reauth', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'user_id', name='uq_provider_user')
    )
    op.create_index(op.f('ix_oauth_tokens_provider'), 'oauth_tokens', ['provider'], unique=False)
    op.create_index(op.f('ix_oauth_tokens_user_id'), 'oauth_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_oauth_tokens_email_address'), 'oauth_tokens', ['email_address'], unique=False)

    op.create_table('raw_emails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.String(length=255), nullable=False),
        sa.Column('thread_id', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=1024), nullable=True),
        sa.Column('sender', sa.String(length=512), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('snippet', sa.Text(), nullable=True),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_raw_emails_email_id'), 'raw_emails', ['email_id'], unique=True)

    op.create_table('transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('merchant', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('source_details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('recurring_subscription_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['recurring_subscription_id'], ['recurring_subscriptions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_date'), 'transactions', ['date'], unique=False)
    op.create_index(op.f('ix_transactions_id'), 'transactions', ['id'], unique=False)
    op.create_index(op.f('ix_transactions_merchant'), 'transactions', ['merchant'], unique=False)

    op.create_table('parsed_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=8), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('raw_email_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['raw_email_id'], ['raw_emails.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('actions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('actions')
    op.drop_table('parsed_events')
    op.drop_index(op.f('ix_transactions_merchant'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_id'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_date'), table_name='transactions')
    op.drop_table('transactions')
    op.drop_index(op.f('ix_raw_emails_email_id'), table_name='raw_emails')
    op.drop_table('raw_emails')
    op.drop_index(op.f('ix_oauth_tokens_email_address'), table_name='oauth_tokens')
    op.drop_index(op.f('ix_oauth_tokens_user_id'), table_name='oauth_tokens')
    op.drop_index(op.f('ix_oauth_tokens_provider'), table_name='oauth_tokens')
    op.drop_table('oauth_tokens')
    op.drop_index(op.f('ix_gmail_tokens_user_id'), table_name='gmail_tokens')
    op.drop_index(op.f('ix_gmail_tokens_id'), table_name='gmail_tokens')
    op.drop_table('gmail_tokens')
    op.drop_index(op.f('ix_tasks_name'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_id'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_index(op.f('ix_recurring_subscriptions_merchant'), table_name='recurring_subscriptions')
    op.drop_index(op.f('ix_recurring_subscriptions_id'), table_name='recurring_subscriptions')
    op.drop_table('recurring_subscriptions')


