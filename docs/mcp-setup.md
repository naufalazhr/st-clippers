# Menjalankan Sultan Clip dari Telegram (Hermes + MCP)

Panduan operasional: menghubungkan Sultan Clip ke Hermes Agent lewat MCP, lalu
mengendalikannya dari Telegram. Untuk latar belakang arsitekturnya lihat
[`mcp-agent-integration-playbook.md`](./mcp-agent-integration-playbook.md).

```
Telegram  ◄── long polling ──►  Hermes Agent ── MCP ──► 127.0.0.1:<port>  Sultan Clip
(HP)                            (mesin yang sama)                         (tray)
```

Hermes memakai `getUpdates`, jadi bot menghubungi Telegram keluar — **tidak perlu
IP publik, port forwarding, atau sertifikat HTTPS**.

---

## 1. Nyalakan MCP di Sultan Clip

1. Buka Sultan Clip → **Settings** di sidebar.
2. Aktifkan **Akses Agent (MCP)**.
3. Layar akan menampilkan alamat dan token. **Keduanya unik per instalasi** —
   jangan menyalinnya dari dokumen mana pun, termasuk yang ini.

Layar itu juga memperingatkan kalau portnya berpindah. Itu penting: kalau port
berubah, konfigurasi Hermes yang lama menunjuk ke alamat kosong, dan gejalanya
sama persis dengan "aplikasinya tidak jalan".

> Setelah MCP aktif, menutup jendela akan **menyembunyikan** aplikasi ke tray,
> bukan menutupnya — backend harus tetap hidup untuk melayani agent. Keluar
> sepenuhnya lewat klik kanan ikon tray → **Keluar**. Kalau MCP nonaktif,
> menutup jendela tetap menutup aplikasi seperti biasa.

## 2. Hubungkan Hermes

Salin blok YAML dari layar Settings (tombol salin di sebelah kanan):

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  sultan_clip:
    url: "http://127.0.0.1:8765/mcp"   # pakai port yang tampil di Settings
    headers:
      Authorization: "Bearer <token dari layar Settings>"
```

Restart Hermes setelah mengubah file ini.

Kalau agent-mu dikonfigurasi lewat percakapan dan bukan file, layar Settings juga
menyediakan kalimat siap tempel untuk itu.

**Checklist koneksi**

- [ ] Sultan Clip berjalan (cek ikon tray)
- [ ] Toggle MCP **aktif** di Settings
- [ ] URL memakai port yang **sedang terpakai**, bukan yang diingat dari dulu
- [ ] Token tersalin utuh (64 karakter hex)
- [ ] Hermes sudah direstart

Verifikasi cepat dari terminal — ganti `<PORT>` dan `<TOKEN>`:

```bash
# Tanpa token harus ditolak
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:<PORT>/mcp \
  -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"ping"}'
# → 401

# Daftar tool
curl -s -X POST http://127.0.0.1:<PORT>/mcp \
  -H "Authorization: Bearer <TOKEN>" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'
```

## 3. Tool yang tersedia

| Tool | Untuk apa |
|---|---|
| `list_jobs` | "Kemarin aku proses video apa saja?" |
| `get_job` | Status satu job, klip yang sudah jadi, dan cuplikan log. Bisa menunggu lewat `wait_seconds`. |
| `list_clips` | Klip sebuah job, urut dari skor viral tertinggi, lengkap dengan **path file absolut** |
| `get_style_options` | Semua pilihan tampilan beserta nilai yang valid dan default-nya |
| `create_clip_job` | Membuat klip dari sebuah video. Butuh `url`; `topic` sangat memengaruhi bagian mana yang dipilih |
| `restyle_clip` | Render ulang satu klip dengan gaya berbeda (style caption, font, ukuran, warna, framing, transisi, watermark) |

### Yang bisa diatur agent

Sama seperti kontrol di aplikasi: framing (`crop_mode`, `cam_corner`), caption
(`caption_style`, `caption_font`, `caption_font_size`, `caption_position`,
`caption_color`, `caption_outline`, `caption_outline_color`,
`caption_box_opacity`, `burn_subtitles`), `transition`, watermark
(`watermark_text`, posisi, opacity, skala, warna, font), dan saat pembuatan juga
`top`, durasi, `language`, `analyze_seconds`, `required_hashtags`.

Agent sebaiknya memanggil `get_style_options` dulu daripada menebak nama font
atau mode framing — menebak baru ketahuan salah setelah render selesai.

### Yang sengaja TIDAK bisa diubah agent

- **Teks caption hasil transkripsi.** `restyle_clip` hanya mengubah tampilan;
  isi kalimatnya tetap. Mengedit teks dilakukan sendiri di aplikasi lewat
  dialog Edit Caption.
- **API key AI.** Tidak pernah melewati MCP, baik masuk maupun keluar. Job yang
  dibuat lewat agent memakai skor heuristik; skoring AI butuh key yang diatur
  di aplikasi.

`list_clips` dan `get_job` mengembalikan path file lokal supaya Hermes bisa
mengirim videonya langsung ke Telegram (`sendVideo`) tanpa perlu mengunduh ulang.

## 4. Prompt sistem untuk Hermes

Aturan alurnya sudah ada di deskripsi masing-masing tool, tapi menyalinnya ke
prompt sistem Hermes membuat agent jauh lebih patuh:

```
Kalau pengguna minta membuat klip dengan Sultan Clip:
1. Tanyakan dulu link videonya DAN topik yang ingin disorot. Jangan pernah
   mengarang topik — topik menentukan bagian mana yang dipotong, dan salah
   potong berarti membuang beberapa menit render.
2. Panggil create_clip_job. Kalau statusnya "running", beri tahu pengguna bahwa
   prosesnya berjalan, lalu panggil get_job dengan wait_seconds. Jangan diam.
3. Setelah selesai, panggil list_clips dan kirim file videonya langsung
   (sendVideo dengan path lokal), bukan link.
3b. Kalau pengguna minta tampilannya diubah (misal "captionnya bikin kotak
   hitam" atau "fontnya kegedean"), panggil get_style_options untuk memetakan
   maunya ke nilai yang valid, lalu restyle_clip. Jangan menebak nama font.
   Kalau yang diminta adalah mengubah kata-katanya, bilang bahwa itu diedit
   sendiri di aplikasi.
4. Sebutkan skor viral dan alasannya untuk tiap klip supaya pengguna tahu mana
   yang sebaiknya diunggah duluan.
5. Sebelum menawarkan render ulang, panggil list_clips dulu — klip yang sudah
   ada tidak perlu dibuat lagi.
Jangan menjawab pertanyaan soal status dari ingatan: selalu panggil ulang
get_job, karena kondisinya berubah terus selama render berjalan.
```

## 5. Batas yang sengaja dipasang

- **Satu job sekaligus.** Render sudah memakai seluruh CPU; job kedua hanya
  membuat keduanya lambat. Permintaan kedua ditolak dengan pesan yang jelas.
- **Maksimal 6 job per jam**, sebagai rem kalau agent terjebak loop.
- **`create_clip_job` tanpa `url` bukan error**, tapi balasan `needs_input` yang
  memberi tahu agent apa yang harus ditanyakan ke pengguna.

## 6. Kalau ada beberapa MCP host sekaligus

Port default `8765` sering dipakai aplikasi lain. Sultan Clip akan mencoba 20
port berikutnya, lalu meminta port bebas apa pun ke sistem operasi. Port yang
benar-benar terpakai **disimpan** dan dipakai lagi di peluncuran berikutnya, dan
layar Settings memberi peringatan saat portnya berpindah.

Artinya: kalau agent tiba-tiba tidak bisa terhubung, buka Settings dan salin
ulang URL-nya.

## 7. Batasan keamanan

- Listener hanya mengikat `127.0.0.1` — tidak bisa dijangkau dari luar mesin.
- Token 32 byte acak per instalasi, di `<data-dir>/mcp-token`, mode `0600` di
  Unix, dibandingkan secara constant-time, bisa dibuat ulang dari Settings.
- **Batasnya adalah "satu user OS yang sama"**: program apa pun yang berjalan
  sebagai user kamu bisa membaca token itu dan memakai tool-nya.
- MCP **mati sampai dinyalakan**.
- Kalau beberapa orang bisa mengirim pesan ke bot Telegram-mu, **Hermes yang
  harus melakukan otorisasi** (allow-list Telegram user id). Sultan Clip hanya
  tahu satu instalasi dan tidak bisa membedakan dua pengguna Telegram.

## 8. Gejala dan penyebab

| Gejala | Penyebab | Perbaikan |
|---|---|---|
| Agent: "connection refused" | Aplikasi tidak jalan, MCP mati, atau **portnya pindah** | Buka Settings, salin ulang URL |
| `401` di semua panggilan | Token terpotong saat disalin, atau sudah diregenerasi | Salin ulang dari Settings, restart Hermes |
| Tool jalan tapi klip tidak terkirim | Agent mengirim link, bukan file | Pakai `path` dari `list_clips` dengan `sendVideo` |
| Agent melaporkan status basi | Ia menjawab dari ingatan | Tambahkan aturan nomor 5 di prompt sistem |
| Job kedua ditolak | Batas satu job sekaligus | Tunggu job pertama selesai |
