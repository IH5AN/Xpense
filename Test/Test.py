import streamlit as st
import sqlite3
import bcrypt
import pandas as pd
import plotly.express as px
from PIL import Image
import base64
import io
from datetime import datetime
from prophet import Prophet
import streamlit.components.v1 as components
import hashlib
from io import BytesIO
# import calendar # Removed as it's no longer used after removing laporan_page
st.set_page_config(
    page_title="Xpense",
    layout="wide",
    page_icon="Xpense V5.png"
)

# --- Database Connection ---
DB_NAME = "users.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        profile_pic BLOB,
        emergency_rate INTEGER DEFAULT 10,
        nama_akun TEXT
    )
    """)

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN nama_akun TEXT")
    except sqlite3.OperationalError:
        # Jika kolom sudah ada, abaikan error
        pass
        
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS laporan_keuangan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        tanggal TEXT,
        kategori TEXT,
        jenis TEXT,
        jumlah INTEGER,
        dana_darurat INTEGER,
        keterangan TEXT,
        bukti_img BLOB
    )
    """)

    # --- Inisialisasi Tabel Target Jika Belum Ada ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS target_anggaran (
            username TEXT,
            bulan TEXT,
            tahun INTEGER,
            target_pengeluaran INTEGER,
            target_tabungan INTEGER,
            target_investasi INTEGER,
            PRIMARY KEY (username, bulan, tahun)
        )
    """)
    conn.commit()
    conn.close()

def get_user_settings(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT emergency_rate, profile_pic FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result

# --- Login / Register Page ---
def login_register_page():
    st.markdown("<h1 style='text-align: center; color: #4CAF50;'>Selamat Datang di Aplikasi Xpense</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; font-size: 18px;'>Kelola keuangan Anda dengan lebih mudah dan cerdas!</p>", unsafe_allow_html=True)

    # Centering the login/register form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["Masuk", "Daftar"])

        with tab1:
            st.subheader("Masuk ke Akun Anda")
            username_login = st.text_input("Username", key="username_login")
            password_login = st.text_input("Password", type="password", key="password_login")

            if st.button("Login", use_container_width=True):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username_login,))
                user_data = cursor.fetchone()
                conn.close()

                if user_data:
                    if bcrypt.checkpw(password_login.encode('utf-8'), user_data[0]):
                        st.session_state["logged_in"] = True
                        st.session_state["username"] = username_login
                        st.session_state["current_page"] = "Home" # Redirect to home after login
                        st.success("✅ Login Berhasil!")
                        st.rerun()
                    else:
                        st.error("Username atau password salah.")
                else:
                    st.error("Username atau password salah.")

        with tab2:
            st.subheader("Daftar Akun Baru")
            username_register = st.text_input("Username", key="username_register")
            password_register = st.text_input("Password", type="password", key="password_register")
            confirm_password_register = st.text_input("Konfirmasi Password", type="password", key="confirm_password_register")

            if st.button("Daftar", use_container_width=True):
                if not username_register or not password_register or not confirm_password_register:
                    st.warning("Mohon lengkapi semua kolom.")
                elif password_register != confirm_password_register:
                    st.error("Password dan konfirmasi password tidak cocok.")
                else:
                    conn = get_connection()
                    cursor = conn.cursor()
                    
                    # Check if username already exists
                    cursor.execute("SELECT * FROM users WHERE username = ?", (username_register,))
                    if cursor.fetchone():
                        st.error("Username sudah ada. Mohon gunakan username lain.")
                    else:
                        hashed_password = bcrypt.hashpw(password_register.encode('utf-8'), bcrypt.gensalt())
                        cursor.execute("INSERT INTO users (username, password_hash, nama_akun) VALUES (?, ?, ?)", 
                                       (username_register, hashed_password, username_register)) # Default nama_akun to username
                        conn.commit()
                        st.success("✅ Registrasi Berhasil! Silakan Login.")
                    conn.close()

# --- Logout Confirmation Page ---
def logout_confirmation_page():
    st.sidebar.warning("Anda yakin ingin keluar?")
    col_yes, col_no = st.sidebar.columns(2)
    if col_yes.button("Ya, Keluar"):
        st.session_state["logged_in"] = False
        st.session_state["username"] = None
        st.session_state["confirm_logout"] = False
        st.session_state["current_page"] = "Login" # Redirect to login page
        st.info("Anda telah berhasil keluar.")
        st.rerun()
    if col_no.button("Tidak"):
        st.session_state["confirm_logout"] = False
        st.rerun()

# --- Fungsi-fungsi Halaman Aplikasi ---
def angka_input_with_format(label, key="formatted_input"):
    st.markdown(f"<label>{label}</label>", unsafe_allow_html=True)
    html_code = f"""
    <script>
    function formatNumber(input) {{
        var value = input.value.replace(/[^0-9]/g, '');
        if (value) {{
            input.value = parseInt(value).toLocaleString('id-ID');
        }} else {{
            input.value = '';
        }}
    }}
    </script>
    <input id="{key}" type="text" oninput="formatNumber(this)" placeholder="Contoh: 100000" style="padding: 0.5rem; width: 100%; border-radius: 5px; border: 1px solid #ccc;">
    <script>
        const input = window.parent.document.getElementById("{key}");
        input?.addEventListener("input", function() {{
            const value = input.value.replaceAll('.', '');
            window.parent.postMessage({{ type: "streamlit:setComponentValue", key: "{key}", value: value }}, "*");
        }});
    </script>
    """
    value = components.html(html_code, height=60)
    return value

def home_page():
    username = st.session_state["username"]

    # Ambil nama akun dan foto di pojok kiri atas
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nama_akun, profile_pic FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    nama_akun = result[0] if result and result[0] else username
    profile_pic = result[1] if result else None

    # Tampilkan salam dan foto
    col1, col2 = st.columns([0.1, 0.9])
    with col1:
        if profile_pic:
            encoded = base64.b64encode(profile_pic).decode()
            st.markdown(
                f"""<img src="data:image/png;base64,{encoded}" 
                        style="width: 50px; height: 50px; border-radius: 50%; border: 2px solid #4CAF50;">""",
                unsafe_allow_html=True
            )
    with col2:
        st.markdown(f"<h5>👋 Halo, {nama_akun}!</h5>", unsafe_allow_html=True)

    st.title("🏠 Home - Input Data Keuangan")

    # Inisialisasi atau update key untuk mereset form
    if "input_key" not in st.session_state:
        st.session_state["input_key"] = 0

    tanggal = st.date_input("Tanggal Transaksi", value=datetime.now().date(), key=f"tanggal_{st.session_state['input_key']}")
    
    # Menambahkan opsi 'Pilih' pada selectbox Jenis
    jenis = st.selectbox("Jenis", ["Pilih", "Pendapatan", "Pengeluaran"], key=f"jenis_{st.session_state['input_key']}")

    # Menentukan opsi kategori berdasarkan jenis yang dipilih, dan menambahkan 'Pilih'
    kategori_options = []
    if jenis == "Pilih":
        kategori_options = ["Pilih"]
    elif jenis == "Pendapatan":
        kategori_options = ["Pilih", "Keuntungan"]
    else: # jenis == "Pengeluaran"
        kategori_options = ["Pilih", "Listrik", "Gaji", "PDAM", "Bahan Baku", "Sewa Tempat", "Lain-lain"]
    
    kategori_index = 0
    if kategori_options and "Pilih" in kategori_options:
        kategori_index = kategori_options.index("Pilih")

    kategori = st.selectbox("Kategori", kategori_options, index=kategori_index, key=f"kategori_{st.session_state['input_key']}")

    def format_angka_indonesia(angka_str):
        try:
            # Handle empty string or string with only non-numeric characters
            if not any(char.isdigit() for char in angka_str):
                return angka_str
            angka = int(angka_str.replace(".", "").replace(",", ""))
            return "{:,.0f}".format(angka).replace(",", ".")
        except ValueError:
            return angka_str # Return original if conversion fails for non-numeric input

    jumlah_input = st.text_input("Jumlah (Rp)", placeholder="Contoh: 100000", key=f"jumlah_input_{st.session_state['input_key']}")

    if jumlah_input:
        formatted_display = format_angka_indonesia(jumlah_input)
        st.write(f"Jumlah Nilai yang Di Input: Rp {formatted_display}")

    # Dana Darurat Settings
    username = st.session_state["username"]
    emergency_rate_from_db, _ = get_user_settings(username) # Renamed to avoid conflict

    # Set initial_slider_value to 5 for new submissions
    initial_slider_value = emergency_rate_from_db if emergency_rate_from_db is not None else 5 

    new_rate = st.slider("Persentase Dana Darurat (%)", 5, 10, value=initial_slider_value, key=f"emergency_rate_slider_{st.session_state['input_key']}")
    
    if new_rate != emergency_rate_from_db: # Compare with the value from DB
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET emergency_rate = ? WHERE username = ?", (new_rate, username))
        conn.commit()
        conn.close()
        st.rerun() # Add this line to make the change immediate

    keterangan = st.text_input("Keterangan (Opsional)", key=f"keterangan_{st.session_state['input_key']}")

    bukti_img = None
    uploaded_img = st.file_uploader("Upload Bukti Gambar (opsional)", type=["png", "jpg", "jpeg"], key=f"bukti_img_{st.session_state['input_key']}")
    if uploaded_img:
        bukti_img = uploaded_img.read()


    if st.button("Simpan Data"):
        if not jumlah_input:
            st.warning("Jumlah tidak boleh kosong.")
            return
        if jenis == "Pilih":
            st.warning("Silakan pilih Jenis transaksi.")
            return
        if kategori == "Pilih":
            st.warning("Silakan pilih Kategori transaksi.")
            return

        try:
            jumlah = int(jumlah_input.replace(".", "").replace(",", ""))
            username = st.session_state["username"]
            # Use the 'new_rate' from the slider for calculation
            dana_darurat = int(jumlah * (new_rate / 100)) if jenis == "Pendapatan" else 0

            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO laporan_keuangan (username, tanggal, kategori, jenis, jumlah, dana_darurat, keterangan, bukti_img)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, tanggal.isoformat(), kategori, jenis, jumlah, dana_darurat, keterangan, bukti_img))
            conn.commit()
            conn.close()
            st.success("✅ Data berhasil disimpan.")
            # Increment key to reset all input widgets after successful submission
            st.session_state["input_key"] += 1
            st.session_state["reset_report_filters"] = True # Set flag to reset report filters
            st.rerun()
        except ValueError:
            st.error("Jumlah harus berupa angka valid, contoh: 100000")
        except Exception as e:
            st.error(f"Terjadi kesalahan: {e}")


def generate_forecasting_insights(df_forecast, periods, data_type):
    insights = []
    
    # Filter forecast to only include future predictions
    future_forecast = df_forecast.tail(periods)

    if future_forecast.empty:
        insights.append(f"Tidak ada data forecast {data_type} di masa depan untuk dianalisis.")
        return insights

    # Get the last historical value for comparison (from the part of df_forecast that's not future)
    # We assume 'ds' is sorted and the last 'periods' rows are the future.
    # So the last historical point would be just before the future period starts.
    if len(df_forecast) > periods:
        last_historical_value = df_forecast['yhat'].iloc[len(df_forecast) - periods - 1]
    else:
        # This case implies df_forecast largely consists of future data or very few historical points.
        # If there's only future data, we can't compare to historical. Adjust this logic as needed.
        if len(df_forecast) > 0: # If there's at least one data point
             last_historical_value = df_forecast['yhat'].iloc[0] # Take the earliest if only future or very few points
        else:
            last_historical_value = 0 # Default if no data at all


    # Calculate the average forecast for the future days
    avg_forecast_future = future_forecast['yhat'].mean()

    # Calculate the change from the last historical value to the end of the forecast period
    final_forecast_value = future_forecast['yhat'].iloc[-1]
    change = final_forecast_value - last_historical_value
    
    # Trend Analysis
    if change > 0:
        insights.append(f"{data_type.capitalize()} Anda diperkirakan akan menunjukkan tren meningkat dalam {periods} hari ke depan, dengan estimasi kenaikan sekitar Rp {change:,.0f} dari periode terakhir yang tercatat.")
    elif change < 0:
        insights.append(f"{data_type.capitalize()} Anda diperkirakan akan menunjukkan tren menurun dalam {periods} hari ke depan, dengan estimasi penurunan sekitar Rp {abs(change):,.0f} dari periode terakhir yang tercatat.")
    else:
        insights.append(f"{data_type.capitalize()} Anda diperkirakan akan cenderung stabil dalam {periods} hari ke depan.")

    # Volatility/Uncertainty Analysis
    # The range of uncertainty (yhat_upper - yhat_lower)
    avg_uncertainty_range = (future_forecast['yhat_upper'] - future_forecast['yhat_lower']).mean()
    if avg_forecast_future != 0: # Avoid division by zero
        if avg_uncertainty_range < abs(avg_forecast_future) * 0.1: # Example threshold: less than 10% of average forecast
            insights.append(f"Model menunjukkan tingkat kepercayaan yang tinggi terhadap prediksi ini, dengan rata-rata rentang ketidakpastian sekitar Rp {avg_uncertainty_range:,.0f} per hari.")
        elif avg_uncertainty_range < abs(avg_forecast_future) * 0.3: # Example threshold: less than 30%
            insights.append(f"Prediksi memiliki tingkat kepercayaan moderat, dengan rata-rata rentang ketidakpastian sekitar **Rp {avg_uncertainty_range:,.0f} per hari. Fluktuasi kecil mungkin terjadi.")
        else:
            insights.append(f"Ada ketidakpastian yang cukup tinggi dalam prediksi ini, dengan rata-rata rentang ketidakpastian sekitar Rp {avg_uncertainty_range:,.0f} per hari. Ini bisa disebabkan oleh data historis yang bervariasi. Pertimbangkan untuk menambahkan lebih banyak data atau memeriksa anomali.")
    else:
        insights.append(f"Tidak dapat menganalisis volatilitas karena {data_type} rata-rata yang diperkirakan adalah nol.")

    # Seasonal Analysis (simple check for daily/weekly patterns if present)
    max_forecast_future = future_forecast['yhat'].max()
    min_forecast_future = future_forecast['yhat'].min()
    
    if avg_forecast_future != 0 and (max_forecast_future - min_forecast_future) > (abs(avg_forecast_future) * 0.2): # If fluctuation is more than 20% of avg
        insights.append(f"Terdapat indikasi pola musiman dalam {data_type}, dengan fluktuasi antara Rp {min_forecast_future:,.0f} dan Rp {max_forecast_future:,.0f} dalam {periods} hari ke depan. Perhatikan hari-hari atau periode tertentu yang mungkin memiliki {data_type} lebih tinggi atau lebih rendah.")
    else:
        insights.append(f"Pola musiman yang signifikan tidak terlalu terlihat dalam periode prediksi ini, menunjukkan {data_type} yang cenderung lebih konsisten dari hari ke hari.")

    return insights


def dashboard_page():
    st.title("📊 Dashboard Keuangan")
    username = st.session_state["username"]
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM laporan_keuangan WHERE username = ?", conn, params=(username,))
    conn.close()

    if df.empty:
        st.info("Tidak ada data.")
        return

    df["tanggal"] = pd.to_datetime(df["tanggal"])
    df["jenis"] = df["jenis"].str.lower()

    # --- Filtering Section (Using columns for horizontal layout) ---
    st.subheader("Filter Data")
    col_jenis, col_kategori, col_waktu = st.columns(3)

    with col_jenis:
        jenis_filter = st.selectbox("Jenis Data", ["Semua", "Pendapatan", "Pengeluaran"], key="jenis_filter_dashboard")

    with col_kategori:
        kategori_unik = sorted(df["kategori"].unique())
        kategori_filter = st.selectbox("Kategori", ["Semua"] + kategori_unik, key="kategori_filter_dashboard")

    with col_waktu:
        filter_mode = st.selectbox("Filter Waktu", ["Semua", "Hari", "Bulan", "Tahun", "Rentang Tanggal"], key="waktu_filter_dashboard")

    filtered_df = df.copy()

    if jenis_filter != "Semua":
        filtered_df = filtered_df[filtered_df["jenis"] == jenis_filter.lower()]

    if kategori_filter != "Semua":
        filtered_df = filtered_df[filtered_df["kategori"] == kategori_filter]

    if filter_mode == "Hari":
        selected_date = st.date_input("Pilih Tanggal", key="date_input_dashboard")
        if selected_date:
            filtered_df = filtered_df[filtered_df["tanggal"].dt.date == selected_date]
    elif filter_mode == "Bulan":
        bulan_list = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        unique_months_in_data = sorted(filtered_df["tanggal"].dt.month.unique())
        display_months = [bulan_list[m-1] for m in unique_months_in_data]
        if display_months:
            selected_month_name = st.selectbox("Pilih Bulan", display_months, key="month_selectbox_dashboard")
            selected_month_num = bulan_list.index(selected_month_name) + 1
            filtered_df = filtered_df[filtered_df["tanggal"].dt.month == selected_month_num]
        else:
            st.info("Tidak ada data bulan yang tersedia untuk difilter.")
            filtered_df = pd.DataFrame()
    elif filter_mode == "Tahun":
        unique_years = sorted(filtered_df["tanggal"].dt.year.unique())
        if unique_years:
            selected_year = st.selectbox("Pilih Tahun", unique_years, key="year_selectbox_dashboard")
            filtered_df = filtered_df[filtered_df["tanggal"].dt.year == selected_year]
        else:
            st.info("Tidak ada data tahun yang tersedia untuk difilter.")
            filtered_df = pd.DataFrame()
    elif filter_mode == "Rentang Tanggal":
        date_range = st.date_input("Pilih Rentang Tanggal", [], key="date_range_dashboard")
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[(filtered_df["tanggal"] >= pd.to_datetime(start_date)) & (filtered_df["tanggal"] <= pd.to_datetime(end_date))]
        elif len(date_range) == 1:
            st.info("Pilih rentang tanggal (dua tanggal) atau satu tanggal untuk filter harian.")
            filtered_df = pd.DataFrame()

    if filtered_df.empty:
        st.info("Tidak ada data untuk filter yang dipilih.")
        return

    # Assign filtered_df back to df for the rest of the dashboard calculations
    df = filtered_df

    # --- Ringkasan Keuangan ---
    st.subheader("📋 Ringkasan Keuangan Anda")
    total_pendapatan = df[df["jenis"] == "pendapatan"]["jumlah"].sum()
    total_pengeluaran = df[df["jenis"] == "pengeluaran"]["jumlah"].sum()
    keuntungan_bersih = total_pendapatan - total_pengeluaran

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(label="💰 Total Pendapatan", value=f"Rp {total_pendapatan:,.0f}".replace(",", "."))
        st.markdown(
            """
            <style>
            [data-testid="stMetricValue"] {
                font-size: 24px;
                color: #4CAF50;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.metric(label="💸 Total Pengeluaran", value=f"Rp {total_pengeluaran:,.0f}".replace(",", "."))
        st.markdown(
            """
            <style>
            [data-testid="stMetricValue"] {
                font-size: 24px;
                color: #F44336;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        if keuntungan_bersih >= 0:
            st.metric(label="📊 Keuntungan Bersih", value=f"Rp {keuntungan_bersih:,.0f}".replace(",", "."), delta="👍 Cukup Baik!" if keuntungan_bersih > 0 else None)
        else:
            st.metric(label="📊 Rugi Bersih", value=f"Rp {abs(keuntungan_bersih):,.0f}".replace(",", "."), delta="👎 Perlu Perhatian!")

    st.markdown("---")
    st.info(f"Ringkasan ini mencakup data dari tanggal {df['tanggal'].min().strftime('%d %b %Y')} hingga {df['tanggal'].max().strftime('%d %b %Y')}.")

    # --- Simplified Line Chart and Pie Chart Side-by-Side ---
    st.subheader("Visualisasi Data Keuangan")
    chart_col1, chart_col2 = st.columns(2) # Create two columns for charts

    with chart_col1:
        # Line Chart: Tren Harian (Simplified)
        if jenis_filter == "Pendapatan":
            y_data = ["pendapatan"]
        elif jenis_filter == "Pengeluaran":
            y_data = ["pengeluaran"]
        else:
            y_data = ["pendapatan", "pengeluaran"]

        daily_summary = df.groupby(["tanggal", "jenis"])["jumlah"].sum().unstack().fillna(0)
        # Ensure 'pendapatan' and 'pengeluaran' columns exist even if no data for them
        if 'pendapatan' not in daily_summary.columns:
            daily_summary['pendapatan'] = 0
        if 'pengeluaran' not in daily_summary.columns:
            daily_summary['pengeluaran'] = 0
        
        daily_summary = daily_summary.reset_index()

        fig_line = px.line(daily_summary, x="tanggal", y=y_data, markers=False, # Removed markers for simplification
                      title="Tren Harian",
                      labels={"value": "Jumlah", "tanggal": "Tanggal"},
                      color_discrete_map={"pendapatan": "#4CAF50", "pengeluaran": "#F44336"})
        fig_line.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20)) # Adjust layout
        st.plotly_chart(fig_line, use_container_width=True)

    with chart_col2:
        # Pie Chart: Distribusi Kategori (Simplified)
        kategori_sum = df.groupby("kategori")["jumlah"].sum().reset_index()
        kategori_sum.columns = ["Kategori", "Total Jumlah"]

        if not kategori_sum.empty:
            fig_pie = px.pie(
                kategori_sum,
                names="Kategori",
                values="Total Jumlah",
                title="Distribusi Total Jumlah per Kategori",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20)) # Adjust layout
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Tidak ada data yang tersedia untuk distribusi kategori.")

    st.markdown("---")


    st.subheader("📈 Forecasting")
    
    # New selectbox for forecasting type
    forecast_type = st.selectbox("Pilih jenis data untuk Forecasting:", ["Pendapatan", "Pengeluaran", "Keuntungan (Pendapatan - Pengeluaran)"])
    
    # Slider for number of forecast days
    forecast_periods = st.slider("Pilih berapa hari ke depan untuk prediksi:", 1, 365, 30)
    
    # Button to run forecasting
    if st.button("Jalankan Forecasting"):
        df_for_forecast = pd.DataFrame()
        data_type_label = ""

        if forecast_type == "Pendapatan":
            df_for_forecast = df[df["jenis"] == "pendapatan"].copy()
            df_for_forecast = df_for_forecast.groupby("tanggal")["jumlah"].sum().reset_index()
            data_type_label = "pendapatan"
        elif forecast_type == "Pengeluaran":
            df_for_forecast = df[df["jenis"] == "pengeluaran"].copy()
            df_for_forecast = df_for_forecast.groupby("tanggal")["jumlah"].sum().reset_index()
            data_type_label = "pengeluaran"
        elif forecast_type == "Keuntungan (Pendapatan - Pengeluaran)":
            df_pendapatan_daily_df = df[df["jenis"] == "pendapatan"].groupby("tanggal")["jumlah"].sum().reset_index()
            df_pengeluaran_daily_df = df[df["jenis"] == "pengeluaran"].groupby("tanggal")["jumlah"].sum().reset_index()
            
            # Merge to get all dates and corresponding amounts
            merged_df = pd.merge(df_pendapatan_daily_df, df_pengeluaran_daily_df, 
                                 on='tanggal', how='outer', suffixes=('_pendapatan', '_pengeluaran'))
            
            # Fill NaN values with 0
            merged_df = merged_df.fillna(0)
            
            # Calculate net amount
            merged_df['jumlah'] = merged_df['jumlah_pendapatan'] - merged_df['jumlah_pengeluaran']
            
            df_for_forecast = merged_df[['tanggal', 'jumlah']]
            data_type_label = "keuntungan"

        df_for_forecast.columns = ["ds", "y"]  # Rename columns for Prophet
        df_for_forecast["ds"] = pd.to_datetime(df_for_forecast["ds"]) # Ensure 'ds' is datetime

        # Check if there are enough data points for Prophet
        if len(df_for_forecast) >= 2:
            try:
                # Create and fit the model
                model = Prophet()
                # Add seasonality if data duration is sufficient
                if (df_for_forecast['ds'].max() - df_for_forecast['ds'].min()).days >= 365 * 2: # At least 2 years for yearly
                    model.add_seasonality(name='yearly', period=365.25, fourier_order=10)
                if (df_for_forecast['ds'].max() - df_for_forecast['ds'].min()).days >= 7 * 2: # At least 2 weeks for weekly
                    model.add_seasonality(name='weekly', period=7, fourier_order=3)


                model.fit(df_for_forecast)

                # Create future dates for forecasting
                future = model.make_future_dataframe(periods=forecast_periods)  # Use selected periods
                forecast = model.predict(future)

                # Plot the forecast
                fig_forecast = model.plot(forecast)
                st.write(fig_forecast)
                
                # Penjelasan untuk grafik forecasting
                st.markdown("""
                    <h5 style='color: #4CAF50;'>Memahami Grafik Forecasting:</h5>
                    <ul>
                        <li><b style='color: #1a73e8;'>Garis Biru Tua:</b> Ini adalah prediksi (<i>yhat</i>) atau estimasi terbaik dari pendapatan/pengeluaran/keuntungan Anda di masa depan. Garis ini menunjukkan tren yang diperkirakan oleh model.</li>
                        <li><b style='color: #8ab4f8;'>Area Biru Muda:</b> Area ini mewakili rentang ketidakpastian atau interval kepercayaan dari prediksi (antara <i>yhat_lower</i> dan <i>yhat_upper</i>). Semakin lebar area ini, semakin besar ketidakpastian dalam prediksi.</li>
                        <li><b style='color: #333;'>Titik-titik Hitam:</b> Titik-titik ini adalah data historis aktual Anda yang digunakan oleh model untuk belajar dan membuat prediksi.</li>
                    </ul>
                """, unsafe_allow_html=True)


                # --- Display Insights ---
                st.subheader(f"💡 Insights dari Forecasting {forecast_type}")
                insights = generate_forecasting_insights(forecast, forecast_periods, data_type_label)
                for i, insight in enumerate(insights):
                    st.markdown(f"- {insight}")
                # --- End Display Insights ---

            except Exception as e:
                st.error(f"Terjadi kesalahan saat melakukan forecasting untuk {forecast_type}: {e}. Pastikan data Anda cukup bervariasi dan tidak kosong.")
        else:
            st.info(f"Tidak ada cukup data {forecast_type.lower()} (minimal 2 data poin) untuk melakukan forecasting.")
    # --- End Forecasting Section ---

def riwayat_page():
    st.title("📜 Riwayat Input Keuangan")
    username = st.session_state["username"]
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM laporan_keuangan WHERE username = ?", conn, params=(username,))
    conn.close()

    if df.empty:
        st.warning("Belum ada data.")
        return

    # Convert 'tanggal' to datetime64[ns] once. This allows .dt accessor for filtering.
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors='coerce')

    # Drop rows where 'tanggal' conversion failed (became NaT)
    df.dropna(subset=['tanggal'], inplace=True)

    if df.empty: # Check again if it became empty after dropping NaT
        st.warning("Tidak ada data tanggal yang valid setelah pembersihan.")
        return

    # --- Filtering Section ---
    st.subheader("Filter Riwayat")
    filter_mode = st.selectbox("Pilih Mode Filter", ["Semua", "Hari", "Bulan", "Tahun", "Rentang Tanggal"])

    filtered_df = df.copy() # Create a copy to apply filters

    if filter_mode == "Hari":
        selected_date = st.date_input("Pilih Tanggal")
        if selected_date: # Ensure a date is selected before filtering
            # Compare datetime64[ns] to a date object
            filtered_df = filtered_df[filtered_df["tanggal"].dt.date == selected_date]
    elif filter_mode == "Bulan":
        bulan_list = [
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember"
        ]
        # Get unique months from the dataframe for the selectbox
        unique_months_in_data = sorted(filtered_df["tanggal"].dt.month.unique())
        display_months = [bulan_list[m-1] for m in unique_months_in_data]

        if display_months:
            selected_month_name = st.selectbox("Pilih Bulan", display_months)
            selected_month_num = bulan_list.index(selected_month_name) + 1
            filtered_df = filtered_df[filtered_df["tanggal"].dt.month == selected_month_num]
        else:
            st.info("Tidak ada data bulan yang tersedia untuk difilter.")
            filtered_df = pd.DataFrame() # Empty dataframe if no months

    elif filter_mode == "Tahun":
        unique_years = sorted(filtered_df["tanggal"].dt.year.unique())
        if unique_years:
            selected_year = st.selectbox("Pilih Tahun", unique_years)
            filtered_df = filtered_df[filtered_df["tanggal"].dt.year == selected_year]
        else:
            st.info("Tidak ada data tahun yang tersedia untuk difilter.")
            filtered_df = pd.DataFrame() # Empty dataframe if no years
    elif filter_mode == "Rentang Tanggal":
        date_range = st.date_input("Pilih Rentang Tanggal", [])
        if len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[(filtered_df["tanggal"].dt.date >= start_date) & (filtered_df["tanggal"].dt.date <= end_date)]
        elif len(date_range) == 1:
            st.info("Pilih rentang tanggal (dua tanggal) atau satu tanggal untuk filter harian.")
            filtered_df = pd.DataFrame()

    if filtered_df.empty:
        st.info("Tidak ada data untuk filter yang dipilih.")
        return

    # --- Tabular Display ---
    st.subheader("Tabel Riwayat Keuangan")

    # Prepare DataFrame for display to format numbers and dates
    display_df = filtered_df.copy()
    display_df["jumlah"] = display_df["jumlah"].apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))
    display_df["dana_darurat"] = display_df["dana_darurat"].apply(lambda x: f"Rp {x:,.0f}".replace(",", "."))
    display_df["tanggal"] = display_df["tanggal"].dt.strftime('%d-%m-%Y')

    # Select columns to display and rename them for better readability
    display_df = display_df[[
        "tanggal", "jenis", "kategori", "jumlah", "dana_darurat", "keterangan", "id"
    ]]
    display_df.columns = [
        "Tanggal", "Jenis", "Kategori", "Jumlah", "Dana Darurat", "Keterangan", "ID"
    ]

    # Display the DataFrame (read-only for deletion purposes)
    st.dataframe(display_df, use_container_width=True, hide_index=True)


    st.markdown("---")

    # --- Delete Functionality (wrapped in expander) ---
    with st.expander("🗑 Hapus Transaksi"):
        delete_id = st.text_input("Masukkan ID Transaksi yang ingin dihapus:")
        if st.button("Hapus Transaksi"):
            if delete_id:
                try:
                    delete_id_int = int(delete_id)
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM laporan_keuangan WHERE id = ? AND username = ?", (delete_id_int, username))
                    conn.commit()
                    if cursor.rowcount > 0:
                        st.success(f"✅ Transaksi dengan ID {delete_id} berhasil dihapus.")
                        st.rerun()
                    else:
                        st.error(f"Transaksi dengan ID {delete_id} tidak ditemukan atau Anda tidak memiliki izin untuk menghapusnya.")
                    conn.close()
                except ValueError:
                    st.error("ID harus berupa angka.")
            else:
                st.warning("Mohon masukkan ID Transaksi yang ingin dihapus.")

    st.markdown("---")

    # --- Edit Functionality (wrapped in expander) ---
    with st.expander("✏️ Edit Transaksi"):
        edit_id = st.text_input("Masukkan ID Transaksi yang ingin diedit:")
        
        if edit_id:
            try:
                edit_id_int = int(edit_id)
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM laporan_keuangan WHERE id = ? AND username = ?", (edit_id_int, username))
                entry_to_edit = cursor.fetchone()
                conn.close()

                if entry_to_edit:
                    # Map column names to fetched data
                    columns = ["id", "username", "tanggal", "kategori", "jenis", "jumlah", "dana_darurat", "keterangan", "bukti_img"]
                    entry_dict = dict(zip(columns, entry_to_edit))

                    st.write(f"Mengedit Transaksi ID: {edit_id_int}")

                    # Populate form with current values
                    edited_tanggal = st.date_input("Tanggal Transaksi", value=datetime.strptime(entry_dict["tanggal"], '%Y-%m-%d').date(), key=f"edit_tanggal_{edit_id}")
                    
                    jenis_options = ["Pilih", "Pendapatan", "Pengeluaran"]
                    edited_jenis_index = jenis_options.index(entry_dict["jenis"].capitalize()) if entry_dict["jenis"].capitalize() in jenis_options else 0
                    edited_jenis = st.selectbox("Jenis", jenis_options, index=edited_jenis_index, key=f"edit_jenis_{edit_id}")

                    kategori_options = []
                    if edited_jenis == "Pilih":
                        kategori_options = ["Pilih"]
                    elif edited_jenis == "Pendapatan":
                        kategori_options = ["Pilih", "Keuntungan"]
                    else: # edited_jenis == "Pengeluaran"
                        kategori_options = ["Pilih", "Listrik", "Gaji", "PDAM", "Bahan Baku", "Sewa Tempat", "Lain-lain"]
                    
                    edited_kategori_index = 0
                    if entry_dict["kategori"] in kategori_options:
                        edited_kategori_index = kategori_options.index(entry_dict["kategori"])
                    else:
                        # If current category is not in the options (e.g., changed type), default to 'Pilih'
                        edited_kategori_index = kategori_options.index("Pilih") if "Pilih" in kategori_options else 0


                    edited_kategori = st.selectbox("Kategori", kategori_options, index=edited_kategori_index, key=f"edit_kategori_{edit_id}")
                    
                    edited_jumlah_str = st.text_input("Jumlah (Rp)", value=str(entry_dict["jumlah"]), key=f"edit_jumlah_{edit_id}")
                    
                    # Display current image if exists
                    current_img_bytes = entry_dict["bukti_img"]
                    if current_img_bytes:
                        st.image(current_img_bytes, caption="Bukti Gambar Saat Ini", width=200)
                        if st.checkbox("Hapus Bukti Gambar Saat Ini", key=f"delete_img_checkbox_{edit_id}"):
                            current_img_bytes = None # Set to None if user wants to delete it

                    new_uploaded_img = st.file_uploader("Upload Bukti Gambar Baru (opsional)", type=["png", "jpg", "jpeg"], key=f"edit_bukti_img_{edit_id}")
                    if new_uploaded_img:
                        current_img_bytes = new_uploaded_img.read() # Overwrite with new upload

                    edited_keterangan = st.text_input("Keterangan (Opsional)", value=entry_dict["keterangan"] or "", key=f"edit_keterangan_{edit_id}")

                    if st.button("Simpan Perubahan", key=f"save_edit_button_{edit_id}"):
                        if not edited_jumlah_str:
                            st.warning("Jumlah tidak boleh kosong.")
                            return
                        if edited_jenis == "Pilih":
                            st.warning("Silakan pilih Jenis transaksi yang diedit.")
                            return
                        if edited_kategori == "Pilih":
                            st.warning("Silakan pilih Kategori transaksi yang diedit.")
                            return

                        try:
                            edited_jumlah = int(edited_jumlah_str.replace(".", "").replace(",", ""))
                            
                            # Recalculate dana_darurat based on edited_jenis and updated emergency_rate
                            # Get the current emergency rate from user settings
                            emergency_rate_from_db, _ = get_user_settings(username)
                            edited_dana_darurat = int(edited_jumlah * (emergency_rate_from_db / 100)) if edited_jenis.lower() == "pendapatan" else 0

                            conn = get_connection()
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE laporan_keuangan
                                SET tanggal = ?, kategori = ?, jenis = ?, jumlah = ?, dana_darurat = ?, keterangan = ?, bukti_img = ?
                                WHERE id = ? AND username = ?
                            """, (edited_tanggal.isoformat(), edited_kategori, edited_jenis.lower(), edited_jumlah, edited_dana_darurat, edited_keterangan, current_img_bytes, edit_id_int, username))
                            conn.commit()
                            conn.close()
                            st.success(f"✅ Transaksi ID {edit_id_int} berhasil diperbarui.")
                            st.rerun()
                        except ValueError:
                            st.error("Jumlah harus berupa angka valid, contoh: 100000")
                        except Exception as e:
                            st.error(f"Terjadi kesalahan saat menyimpan perubahan: {e}")

                else:
                    st.warning(f"Transaksi dengan ID {edit_id_int} tidak ditemukan atau Anda tidak memiliki izin untuk mengeditnya.")
            except ValueError:
                st.error("ID harus berupa angka.")
        else:
            st.info("Masukkan ID transaksi untuk mengedit.")


def akun_page():
    st.markdown("<h1 style='text-align: center;'>👤 Akun Saya</h1>", unsafe_allow_html=True)
    username = st.session_state["username"]

    # Get user settings
    emergency_rate, profile_pic = get_user_settings(username)

    # Get nama akun
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nama_akun FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    nama_akun = result[0] if result else ""
    conn.close()

    # FOTO PROFIL
    if profile_pic:
        encoded = base64.b64encode(profile_pic).decode()
        st.markdown(
            f"""<div style='text-align: center;'>
                <img src="data:image/png;base64,{encoded}" 
                        style="width: 200px; height: 200px; border-radius: 50%; border: 3px solid #4CAF50;">
            </div>""",
            unsafe_allow_html=True
        )
    else:
        st.info("Belum ada foto profil. Unggah satu di bawah ini!")

    uploaded_pic = st.file_uploader("Upload Foto Profil Baru", type=["png", "jpg", "jpeg"])
    if uploaded_pic:
        img_bytes = uploaded_pic.read()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET profile_pic = ? WHERE username = ?", (img_bytes, username))
        conn.commit()
        conn.close()
        st.success("✅ Foto profil berhasil diperbarui.")
        st.rerun()

    if profile_pic and st.button("🗑 Hapus Foto Profil"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET profile_pic = NULL WHERE username = ?", (username,))
        conn.commit()
        conn.close()
        st.success("✅ Foto profil dihapus.")
        st.rerun()

    st.markdown("---")

    # NAMA AKUN
    st.subheader("✍ Nama Akun")
    nama_baru = st.text_input("Ubah Nama Akun", value=nama_akun or "")
    if st.button("Simpan Nama Akun"):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET nama_akun = ? WHERE username = ?", (nama_baru, username))
        conn.commit()
        conn.close()
        st.success("✅ Nama akun berhasil disimpan.")
        st.rerun()

    # GANTI USERNAME & PASSWORD
    st.subheader("🔑 Ganti Username & Password")

    with st.expander("Ganti Username"):
        new_username = st.text_input("Username baru", key="new_username_input")
        if st.button("Simpan Username", key="save_username_button"):
            if new_username:
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    # Check if the new username already exists
                    cursor.execute("SELECT username FROM users WHERE username = ?", (new_username,))
                    if cursor.fetchone():
                        st.error("Username baru sudah digunakan. Mohon pilih username lain.")
                    else:
                        cursor.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, username))
                        cursor.execute("UPDATE laporan_keuangan SET username = ? WHERE username = ?", (new_username, username))
                        cursor.execute("UPDATE target_anggaran SET username = ? WHERE username = ?", (new_username, username)) # Update target table as well
                        conn.commit()
                        st.session_state["username"] = new_username
                        st.success("✅ Username berhasil diperbarui.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Gagal memperbarui username: {e}")
                finally:
                    conn.close()

    with st.expander("Ganti Password"):
        current_pw = st.text_input("Password saat ini", type="password", key="current_pw_input")
        new_pw = st.text_input("Password baru", type="password", key="new_pw_input")
        if st.button("Simpan Password", key="save_pw_button"):
            if not current_pw or not new_pw:
                st.warning("Mohon isi semua kolom.")
            else:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
                db_pw = cursor.fetchone()
                if db_pw and bcrypt.checkpw(current_pw.encode(), db_pw[0]):
                    new_hash = bcrypt.hashpw(new_pw.encode(), bcrypt.gensalt())
                    cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (new_hash, username))
                    conn.commit()
                    st.success("✅ Password berhasil diubah.")
                else:
                    st.error("Password saat ini salah.")
                conn.close()

    # HAPUS AKUN
    st.subheader("⚠ Hapus Akun")
    if st.button("🗑 Hapus Akun Saya", help="Tindakan ini tidak bisa dibatalkan"):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            cursor.execute("DELETE FROM laporan_keuangan WHERE username = ?", (username,))
            cursor.execute("DELETE FROM target_anggaran WHERE username = ?", (username,)) # Delete target data
            conn.commit()
            conn.close()
            st.success("Akun dan semua data terkait berhasil dihapus.")
            st.session_state["logged_in"] = False
            st.session_state["username"] = None
            st.session_state["current_page"] = "Login"
            st.rerun() 
        except Exception as e:
            st.error(f"Terjadi kesalahan saat menghapus akun: {e}")


def main():
    initialize_db()
   
    # Initialize session state for login status and current page
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    if "username" not in st.session_state:
        st.session_state["username"] = None
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "Home"
    if "confirm_logout" not in st.session_state:
        st.session_state["confirm_logout"] = False

    # Custom CSS to make sidebar buttons the same size
    st.markdown("""
        <style>
        .stButton > button {
            width: 100%; /* Make buttons take full width of their container */
            display: block; /* Ensure buttons are block level elements */
            margin-bottom: 5px; /* Add some space between buttons */
        }
        .sidebar-button-container .stButton > button {
            width: 150px; /* Adjust this value as needed for your desired fixed width */
            text-align: center;
        }
        </style>
    """, unsafe_allow_html=True)

    if st.session_state["logged_in"]:
        # Wrap each button in a div with a custom class to apply consistent width
        st.sidebar.markdown('<div class="sidebar-button-container">', unsafe_allow_html=True)
        if st.sidebar.button("🏠 Home"):
            st.session_state["current_page"] = "Home"
            st.session_state["confirm_logout"] = False # Ensure confirmation is hidden
        if st.sidebar.button("📊 Dashboard"):
            st.session_state["current_page"] = "Dashboard"
            st.session_state["confirm_logout"] = False # Ensure confirmation is hidden
        if st.sidebar.button("📜 Riwayat"):
            st.session_state["current_page"] = "Riwayat"
            st.session_state["confirm_logout"] = False # Ensure confirmation is hidden
        # Removed the "🗂️ Laporan" button
        # Removed the "🎯 Target & Anggaran" button
        if st.sidebar.button("👤 Akun"):
            st.session_state["current_page"] = "Akun"
            st.session_state["confirm_logout"] = False # Ensure confirmation is hidden
        
        # Logout confirmation logic
        if st.sidebar.button("🚪 Logout"):
            st.session_state["confirm_logout"] = True
        
        st.sidebar.markdown('</div>', unsafe_allow_html=True) # Close the container

        # Conditional rendering based on confirmation state
        if st.session_state.get("confirm_logout"):
            logout_confirmation_page()
        else:
            # Render the current page based on session state
            if st.session_state["current_page"] == "Home":
                home_page()
            elif st.session_state["current_page"] == "Dashboard":
                dashboard_page()
            elif st.session_state["current_page"] == "Riwayat":
                riwayat_page()
            # Removed the "Laporan" page rendering
            # Removed the "Target & Anggaran" page rendering
            elif st.session_state["current_page"] == "Akun":
                akun_page()
            
    else:
        login_register_page() # Call the new login/register page function

if __name__ == "__main__":
    main()
