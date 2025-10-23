import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "ninja_otc.db"):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                ton_wallet TEXT,
                bank_card TEXT,
                successful_deals INTEGER DEFAULT 0,
                role TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                deal_id TEXT PRIMARY KEY,
                seller_id INTEGER NOT NULL,
                buyer_id INTEGER,
                amount TEXT NOT NULL,
                description TEXT NOT NULL,
                payment_type TEXT NOT NULL,
                payment_address TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (seller_id) REFERENCES users(user_id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_by INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'ton_wallet': row[2],
                'bank_card': row[3],
                'successful_deals': row[4],
                'role': row[5],
                'created_at': row[6]
            }
        return None
    
    def create_or_update_user(self, user_id: int, username: Optional[str] = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, username) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = ?
        """, (user_id, username, username))
        conn.commit()
        conn.close()
    
    def update_user_payment_details(self, user_id: int, ton_wallet: Optional[str] = None, bank_card: Optional[str] = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if ton_wallet is not None:
            cursor.execute("UPDATE users SET ton_wallet = ? WHERE user_id = ?", (ton_wallet, user_id))
        if bank_card is not None:
            cursor.execute("UPDATE users SET bank_card = ? WHERE user_id = ?", (bank_card, user_id))
        
        conn.commit()
        conn.close()
    
    def get_user_role(self, user_id: int) -> str:
        MAX_OWNER = 8200529043
        OWNERS = [625878990]
        
        if user_id == MAX_OWNER:
            return 'max_owner'
        if user_id in OWNERS:
            return 'owner'
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            conn.close()
            return 'admin'
        conn.close()
        return 'user'
    
    def add_admin(self, user_id: int, added_by: int) -> bool:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO admins (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_admin(self, user_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        return rows_affected > 0
    
    def is_owner(self, user_id: int) -> bool:
        role = self.get_user_role(user_id)
        return role in ['max_owner', 'owner']
    
    def is_admin_or_higher(self, user_id: int) -> bool:
        role = self.get_user_role(user_id)
        return role in ['max_owner', 'owner', 'admin']
    
    def create_deal(self, deal_id: str, seller_id: int, amount: str, description: str, 
                    payment_type: str, payment_address: str) -> bool:
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO deals (deal_id, seller_id, amount, description, payment_type, payment_address)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (deal_id, seller_id, amount, description, payment_type, payment_address))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deals WHERE deal_id = ?", (deal_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'deal_id': row[0],
                'seller_id': row[1],
                'buyer_id': row[2],
                'amount': row[3],
                'description': row[4],
                'payment_type': row[5],
                'payment_address': row[6],
                'status': row[7],
                'created_at': row[8],
                'completed_at': row[9]
            }
        return None
    
    def set_deal_buyer(self, deal_id: str, buyer_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE deals SET buyer_id = ? WHERE deal_id = ?", (buyer_id, deal_id))
        conn.commit()
        conn.close()
        return True
    
    def confirm_payment(self, deal_id: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE deals SET status = 'payment_confirmed' WHERE deal_id = ?", (deal_id,))
        conn.commit()
        conn.close()
        return True
    
    def complete_deal(self, deal_id: str) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE deals SET status = 'completed', completed_at = CURRENT_TIMESTAMP 
            WHERE deal_id = ?
        """, (deal_id,))
        
        cursor.execute("SELECT seller_id, buyer_id FROM deals WHERE deal_id = ?", (deal_id,))
        result = cursor.fetchone()
        
        if result:
            seller_id, buyer_id = result
            cursor.execute("UPDATE users SET successful_deals = successful_deals + 1 WHERE user_id = ?", (seller_id,))
            if buyer_id:
                cursor.execute("UPDATE users SET successful_deals = successful_deals + 1 WHERE user_id = ?", (buyer_id,))
        
        conn.commit()
        conn.close()
        return True
    
    def get_all_deals(self) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deals ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        deals = []
        for row in rows:
            deals.append({
                'deal_id': row[0],
                'seller_id': row[1],
                'buyer_id': row[2],
                'amount': row[3],
                'description': row[4],
                'payment_type': row[5],
                'payment_address': row[6],
                'status': row[7],
                'created_at': row[8],
                'completed_at': row[9]
            })
        return deals
    
    def set_user_successful_deals(self, user_id: int, count: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO users (user_id, successful_deals) VALUES (?, ?)", (user_id, count))
        else:
            cursor.execute("UPDATE users SET successful_deals = ? WHERE user_id = ?", (count, user_id))
        
        conn.commit()
        conn.close()
        return True
