# Ninja OTC Bot

## Overview
Ninja OTC is a P2P escrow Telegram bot for safe trading of Telegram gifts, NFTs, tokens, and fiat. Created to replace VaultOtc with improved functionality and security.

## Recent Changes
- **2025-10-23 (v2)**: Updated based on new specifications
  - Changed bot username to @OtcNinjaRobot in deal links
  - Stars deals can now be created without requiring payment details
  - Renamed `/show_deals` to `/deals` command
  - Updated `/deals` output format to show detailed information
  - Improved Stars payment handling with fallback messaging

- **2025-10-23 (v1)**: Initial implementation with full feature set
  - SQLite database for users, deals, and admin management
  - Role-based access control (Max Owner, Owners, Admins, Users)
  - Deal creation and management system
  - Payment confirmation workflow
  - Admin commands for deal and user management

## Project Architecture
- `main.py` - Telegram bot logic with handlers and commands
- `database.py` - SQLite database management layer
- `ninja_otc.db` - SQLite database (auto-created)

## Features
- **User Management**: TON wallet and bank card storage (optional for Stars)
- **Deal Creation**: Generate unique deal links for buyers (@OtcNinjaRobot)
- **Payment Types**: TON wallet, Bank card, or Telegram Stars
- **Payment Tracking**: Admin-only payment confirmation
- **Role System**: 4-tier permission system
- **Deal Completion**: Buyer confirmation workflow

## Configuration
### Required Secrets
- `TELEGRAM_BOT_TOKEN` - Telegram Bot API token from @BotFather

### User Roles
- Max Owner: 8200529043
- Owners: 625878990
- Admins: Added by owners via `/add admin <user_id>`
- Users: Default role

## Commands
- `/start` - Start bot / join deal (with parameter)
- `/buy <deal_id>` - Confirm payment (Admin+)
- `/add admin <user_id>` - Add admin (Owner only)
- `/del admin <user_id>` - Remove admin (Owner only)
- `/set_my_deals <number>` - Set successful deal count (Owner only)
- `/deals` - List all deals with detailed info (Owner only)

## Workflow
1. Seller creates deal → generates unique link (@OtcNinjaRobot)
2. Buyer clicks link → joins deal
3. Seller notified of buyer join
4. Admin confirms payment via `/buy <deal_id>`
5. Seller sends item
6. Buyer confirms receipt → deal completed

## Special Features
- Stars deals can be created without payment details
- Payment address shows TON wallet if available, or "Оплата через Telegram Stars"
- Sellers cannot join their own deals
- Only assigned buyers can confirm receipt
- Deal details hidden from unauthorized users
