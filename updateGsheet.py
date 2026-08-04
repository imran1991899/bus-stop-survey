import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import pandas as pd
import pymysql
from dotenv import load_dotenv

# --- BASE DIRECTORY & ENVIRONMENT SETUP ---
# Identifies the root path of your local GitHub repo directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, 'EDPRS_login.env'))

# Target export folder within your GitHub project repo
EXPORT_DIR = os.path.join(BASE_DIR, 'exports')

class EDPRSApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("EDPRS Wages & Route Data Extractor")
        self.geometry("900x650")
        self.minsize(800, 500)

        # Apply clean visual styling
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        self.current_df = pd.DataFrame() # Store fetched dataset in memory
        self.create_widgets()

    def create_widgets(self):
        # Header Section
        header_frame = ttk.Frame(self, padding=15)
        header_frame.pack(fill=tk.X)
        title_label = ttk.Label(header_frame, text="EDPRS Wages & Route Extractor", font=("Segoe UI", 16, "bold"))
        title_label.pack(anchor=tk.W)
        sub_label = ttk.Label(header_frame, text="Select date range to preview and export route data to Excel.", font=("Segoe UI", 9))
        sub_label.pack(anchor=tk.W)

        # --- Date Filter Parameters ---
        filter_frame = ttk.LabelFrame(self, text=" Date Filter Parameters ", padding=12)
        filter_frame.pack(fill=tk.X, padx=15, pady=(0, 10))

        ttk.Label(filter_frame, text="Start Date (YYYY-MM-DD):", font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=5)
        self.start_date_entry = ttk.Entry(filter_frame, width=15)
        self.start_date_entry.insert(0, "2026-07-28")
        self.start_date_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20), pady=5)

        ttk.Label(filter_frame, text="End Date (YYYY-MM-DD):", font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky=tk.W, padx=(0, 5), pady=5)
        self.end_date_entry = ttk.Entry(filter_frame, width=15)
        self.end_date_entry.insert(0, "2026-08-01")
        self.end_date_entry.grid(row=0, column=3, sticky=tk.W, padx=(0, 20), pady=5)

        # Action Buttons
        self.fetch_btn = ttk.Button(filter_frame, text="🔍 Preview Data", command=self.load_preview_data)
        self.fetch_btn.grid(row=0, column=4, padx=5, pady=5)

        self.export_btn = tk.Button(
            filter_frame, 
            text="📥 Save to Excel", 
            command=self.export_to_excel,
            bg="#2b5797", 
            fg="white", 
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            state=tk.DISABLED
        )
        self.export_btn.grid(row=0, column=5, padx=5, pady=5)

        # --- Data Preview Table Section (Scrollable Treeview) ---
        table_frame = ttk.LabelFrame(self, text=" Data Preview ", padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # Vertical & Horizontal Scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        h_scrollbar = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)

        self.tree = ttk.Treeview(
            table_frame,
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set,
            selectmode="browse"
        )

        v_scrollbar.config(command=self.tree.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        h_scrollbar.config(command=self.tree.xview)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.pack(fill=tk.BOTH, expand=True)

        # Status Bar Footer
        self.status_var = tk.StringVar(value="Ready. Set date criteria and click 'Preview Data'.")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def fetch_db_data(self, start_dt, end_dt):
        """
        Executes updated JOIN query against Azure MySQL.
        """
        host = os.getenv("DB_HOST")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASS")
        database = os.getenv("DB_NAME")
        port = int(os.getenv("DB_PORT", 3306))

        if not all([host, user, password, database]):
            raise ValueError("Database credentials missing in EDPRS_login.env secret file!")

        connection = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            ssl={'ssl': {}}
        )

        try:
            sql = """
                SELECT 
                    wr.wr_busno,
                    wr.captain_id,
                    u.username,
                    u.fullname,
                    wr.depot_id,
                    d.depot_name,
                    MAX(wr.route_id) AS max_route_id,
                    r.route_no
                FROM ds_wages_route wr
                LEFT JOIN depot d 
                    ON CAST(d.depot_id AS CHAR) = CAST(wr.depot_id AS CHAR)
                LEFT JOIN user u 
                    ON u.username = CAST(wr.captain_id AS CHAR)
                LEFT JOIN route r 
                    ON CAST(r.route_id AS CHAR) = CAST(wr.route_id AS CHAR)
                WHERE wr.wr_created >= %s
                  AND wr.wr_created <  %s
                GROUP BY 
                    wr.wr_busno,
                    wr.captain_id,
                    u.username,
                    u.fullname,
                    wr.depot_id,
                    d.depot_name,
                    r.route_no;
            """

            df = pd.read_sql(sql, connection, params=[start_dt, end_dt])
            return df

        finally:
            connection.close()

    def validate_dates(self):
        start_date = self.start_date_entry.get().strip()
        end_date = self.end_date_entry.get().strip()

        try:
            start_dt = f"{start_date} 00:00:00"
            end_dt = f"{end_date} 00:00:00"
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
            return start_dt, end_dt
        except ValueError:
            messagebox.showerror("Error", "Invalid Date format. Please use YYYY-MM-DD format.")
            return None, None

    def load_preview_data(self):
        start_dt, end_dt = self.validate_dates()
        if not start_dt:
            return

        self.status_var.set("Connecting to database and fetching records...")
        self.update_idletasks()

        try:
            self.current_df = self.fetch_db_data(start_dt, end_dt)

            # Clear existing table content
            self.tree.delete(*self.tree.get_children())

            if self.current_df.empty:
                self.status_var.set("No records found for the selected date range.")
                self.export_btn.config(state=tk.DISABLED)
                messagebox.showinfo("Info", "No data returned for this date range.")
                return

            # Setup Treeview Columns dynamically from DataFrame
            columns = list(self.current_df.columns)
            self.tree["columns"] = columns
            self.tree["show"] = "headings"  # Hide default empty first column

            for col in columns:
                self.tree.heading(col, text=col)
                self.tree.column(col, width=110, anchor=tk.CENTER)

            # Insert Data Rows (Fill NaN with empty strings for clean presentation)
            preview_df = self.current_df.fillna("")
            for row in preview_df.itertuples(index=False):
                self.tree.insert("", tk.END, values=list(row))

            self.export_btn.config(state=tk.NORMAL)
            self.status_var.set(f"Loaded {len(self.current_df)} rows successfully.")

        except Exception as e:
            self.status_var.set("Failed to fetch data.")
            messagebox.showerror("Database Error", f"An error occurred:\n{str(e)}")

    def export_to_excel(self):
        if self.current_df.empty:
            messagebox.showwarning("Warning", "No data available to export.")
            return

        # Ensure the output directory inside the repository exists
        os.makedirs(EXPORT_DIR, exist_ok=True)

        # Generate output filename with timestamp
        filename = f"EDPRS_Wages_Route_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        file_path = os.path.join(EXPORT_DIR, filename)

        try:
            self.current_df.to_excel(file_path, index=False, engine='openpyxl')
            self.status_var.set(f"Exported automatically to: {file_path}")
            messagebox.showinfo("Success", f"Excel file successfully saved to GitHub project folder!\n\nLocation:\n{file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save Excel file:\n{str(e)}")

if __name__ == "__main__":
    app = EDPRSApp()
    app.mainloop()
