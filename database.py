import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional


DB_PATH = Path("orderflow_ai.db")


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Create and return a SQLite connection for OrderFlow AI."""
    target = str(db_path or DB_PATH)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    # AI-optimized traceability: keep FK constraints always enabled for integrity.
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """Create core domain tables with FK relations."""
    # AI-optimized traceability: schema is normalized for maintainability and consistency.
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            whatsapp_number TEXT NOT NULL UNIQUE,
            name TEXT,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sku TEXT UNIQUE,
            price REAL NOT NULL CHECK (price >= 0),
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            status TEXT NOT NULL
                CHECK (status IN ('pending', 'confirmed', 'preparing', 'delivered', 'cancelled')),
            total_amount REAL NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        );

        CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK (quantity > 0),
            unit_price REAL NOT NULL CHECK (unit_price >= 0),
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id)
                ON UPDATE CASCADE
                ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        );

        CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items(product_id);
        """
    )
    conn.commit()


def seed_sample_data(conn: sqlite3.Connection) -> None:
    """Insert minimal sample data for local testing."""
    # AI-optimized traceability: idempotent seed via INSERT OR IGNORE.
    with closing(conn.cursor()) as cur:
        cur.executemany(
            """
            INSERT OR IGNORE INTO customers (whatsapp_number, name)
            VALUES (?, ?);
            """,
            [
                ("+905551112233", "Ahmet Yilmaz"),
                ("+905559998877", "Ayse Demir"),
            ],
        )

        cur.executemany(
            """
            INSERT OR IGNORE INTO products (name, sku, price, is_active)
            VALUES (?, ?, ?, ?);
            """,
            [
                ("Limon Kolonyasi 250ml", "HEDIYE-KOLONYA-250", 120.0, 1),
                ("El Kremi 50ml", "HEDIYE-KREM-50", 95.0, 1),
                ("Zeytinyagli Sabun", "HEDIYE-SABUN-1", 70.0, 1),
            ],
        )

        cur.execute(
            """
            INSERT INTO orders (customer_id, status, total_amount)
            SELECT c.id, 'pending', 405.0
            FROM customers c
            WHERE c.whatsapp_number = '+905551112233'
              AND NOT EXISTS (
                  SELECT 1
                  FROM orders o
                  WHERE o.customer_id = c.id
                    AND o.status = 'pending'
              );
            """
        )

        cur.execute(
            """
            SELECT o.id AS order_id
            FROM orders o
            JOIN customers c ON c.id = o.customer_id
            WHERE c.whatsapp_number = '+905551112233' AND o.status = 'pending'
            ORDER BY o.id DESC
            LIMIT 1;
            """
        )
        row = cur.fetchone()
        if row:
            order_id = row["order_id"]
            cur.execute("SELECT COUNT(*) AS item_count FROM order_items WHERE order_id = ?;", (order_id,))
            item_count = cur.fetchone()["item_count"]
            if item_count == 0:
                cur.execute("SELECT id, price FROM products WHERE sku = 'HEDIYE-KOLONYA-250';")
                kolonya = cur.fetchone()
                cur.execute("SELECT id, price FROM products WHERE sku = 'HEDIYE-KREM-50';")
                krem = cur.fetchone()
                cur.execute("SELECT id, price FROM products WHERE sku = 'HEDIYE-SABUN-1';")
                sabun = cur.fetchone()

                if kolonya and krem and sabun:
                    cur.executemany(
                        """
                        INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                        VALUES (?, ?, ?, ?);
                        """,
                        [
                            (order_id, kolonya["id"], 2, kolonya["price"]),
                            (order_id, krem["id"], 1, krem["price"]),
                            (order_id, sabun["id"], 1, sabun["price"]),
                        ],
                    )

    conn.commit()


def init_database(db_path: Optional[Path] = None, with_seed: bool = True) -> None:
    """Initialize database schema and optional seed data."""
    with closing(get_connection(db_path)) as conn:
        create_tables(conn)
        if with_seed:
            seed_sample_data(conn)


if __name__ == "__main__":
    # AI-optimized traceability: one-command bootstrap for local environment setup.
    init_database(with_seed=True)
    print(f"Database initialized at: {DB_PATH.resolve()}")
