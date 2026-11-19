"use strict";

// ---------- util ----------
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const rp = (x) => (x < 0 ? "-" : "") + "Rp" + Math.round(Math.abs(x || 0)).toLocaleString("id-ID");
const num = (x) => Number(x || 0).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const today = () => {
  const d = new Date();
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); // tanggal lokal, bukan UTC
};

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.style.display = "block";
  clearTimeout(toast.h);
  toast.h = setTimeout(() => (t.style.display = "none"), 2500);
}

async function api(path, opt = {}) {
  const res = await fetch(path, {
    ...opt,
    headers: { "Content-Type": "application/json" },
    body: opt.body ? JSON.stringify(opt.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data.detail;
    const msg = Array.isArray(d) ? d.map((e) => `${e.loc.slice(-1)[0]}: ${e.msg}`).join("; ") : d || res.statusText;
    toast("Gagal: " + msg);
    throw new Error(msg);
  }
  return data;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function tabel(kolom, data, aksi) {
  if (!data.length) return '<p class="hint">Belum ada data.</p>';
  const head = kolom.map((k) => `<th class="${k.num ? "num" : ""}">${k.label}</th>`).join("") + (aksi ? "<th></th>" : "");
  const body = data
    .map((r) => {
      const tds = kolom.map((k) => `<td class="${k.num ? "num" : ""}">${k.html ? k.html(r) : esc(k.get ? k.get(r) : r[k.key])}</td>`).join("");
      return `<tr>${tds}${aksi ? `<td class="num">${aksi(r)}</td>` : ""}</tr>`;
    })
    .join("");
  return `<div class="tabel-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function dialog(judul, html) {
  $("#dlg-judul").textContent = judul;
  $("#dlg-isi").innerHTML = html;
  $("#dlg").showModal();
}

// Mode edit untuk form transaksi: menyimpan id yang sedang diedit dan mengubah judul/tombol.
function editor(form, onBatal) {
  const h2 = $("h2", form), judulAsli = h2.textContent;
  const simpan = $('button[type="submit"]', form), labelAsli = simpan.textContent;
  const batal = document.createElement("button");
  batal.type = "button";
  batal.className = "secondary";
  batal.textContent = "Batal edit";
  batal.hidden = true;
  simpan.after(" ", batal);
  let id = null;
  const ed = {
    get id() { return id; },
    mulai(baru, judul) {
      id = baru;
      h2.textContent = judul;
      simpan.textContent = "Simpan perubahan";
      batal.hidden = false;
      form.classList.add("editing");
      form.scrollIntoView({ behavior: "smooth" });
    },
    selesai() {
      id = null;
      h2.textContent = judulAsli;
      simpan.textContent = labelAsli;
      batal.hidden = true;
      form.classList.remove("editing");
    },
    // POST untuk data baru, PUT untuk data yang sedang diedit
    async kirim(path, body) {
      await api(id ? `${path}/${id}` : path, { method: id ? "PUT" : "POST", body });
      toast(id ? "Perubahan tersimpan" : "Tersimpan");
    },
  };
  batal.addEventListener("click", () => {
    const tgl = form.tanggal?.value;
    form.reset();
    if (form.tanggal) form.tanggal.value = tgl;
    ed.selesai();
    onBatal?.();
  });
  return ed;
}

const tombolEdit = (fn, id) => `<button class="link biasa" onclick="${fn}(${id})">Edit</button>`;

async function hapus(path, muat) {
  if (!confirm("Hapus data ini?")) return;
  await api(path, { method: "DELETE" });
  toast("Dihapus");
  await muat();
}
window.hapus = hapus;

// ---------- state ----------
let BAHAN = [];
let PRODUK = [];

async function muatMaster() {
  [BAHAN, PRODUK] = await Promise.all([api("/api/bahan"), api("/api/produk")]);
  const opsiBahan = '<option value="">- pilih -</option>' + BAHAN.map((b) => `<option value="${b.id}">${esc(b.nama)} (${esc(b.satuan)})</option>`).join("");
  for (const sel of document.querySelectorAll('select[name="bahan_id"]')) {
    const v = sel.value;
    sel.innerHTML = opsiBahan;
    sel.value = v;
  }
}

// ---------- tabs ----------
const loaders = {};
document.querySelectorAll("#tabs button").forEach((b) =>
  b.addEventListener("click", async () => {
    document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("active", x === b));
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === "tab-" + b.dataset.tab));
    await muatMaster();
    await loaders[b.dataset.tab]?.();
  })
);

// ---------- laporan ----------
const POS_JUDUL = { pendapatan: "Pendapatan", hpp: "Harga Pokok Penjualan (HPP)", beban: "Beban operasional" };

function blokPos(kode, pos, tanda) {
  const rinci = pos.rincian
    .map((r) => `<div data-pos="${kode}" data-key="${esc(r.key)}" data-nama="${esc(r.nama)}"><span>${esc(r.nama)} <span class="hint">(${num(r.qty)}${kode === "beban" ? " transaksi" : ""})</span></span><span>${rp(r.jumlah)}</span></div>`)
    .join("");
  return `<div class="pos">
    <div class="baris"><span>${tanda}${POS_JUDUL[kode]}</span><span>${rp(pos.total)}</span></div>
    <div class="rumus">Rumus: ${esc(pos.rumus)}<br>Hitungan: <code>${esc(pos.hitungan)}</code></div>
    <div class="rinci">${rinci || '<span class="hint">Tidak ada transaksi.</span>'}</div>
  </div>`;
}

function blokTotal(judul, pos, cls) {
  return `<div class="pos subtotal ${cls || ""}">
    <div class="baris"><span>${judul}</span><span class="${pos.total < 0 ? "neg" : ""}">${rp(pos.total)}</span></div>
    <div class="rumus">Rumus: ${esc(pos.rumus)} &nbsp;|&nbsp; Hitungan: <code>${esc(pos.hitungan)}</code> &nbsp;|&nbsp; Margin: ${pos.margin.toFixed(1)}%</div>
  </div>`;
}

async function muatLaporan() {
  const dari = $("#lr-dari").value, sampai = $("#lr-sampai").value;
  const d = await api(`/api/laporan/laba-rugi?dari=${dari}&sampai=${sampai}`);
  $("#lr-peringatan").innerHTML = d.peringatan.map((p) => `<div class="peringatan">${esc(p)}</div>`).join("");
  $("#lr-isi").innerHTML = `<div class="lr">
    ${blokPos("pendapatan", d.pendapatan, "")}
    ${blokPos("hpp", d.hpp, "(−) ")}
    ${blokTotal("Laba kotor", d.laba_kotor)}
    ${blokPos("beban", d.beban, "(−) ")}
    ${blokTotal("Laba bersih", d.laba_bersih, "akhir")}
  </div>`;
}

$("#lr-isi").addEventListener("click", async (e) => {
  const el = e.target.closest("[data-pos]");
  if (!el) return;
  const { pos, key, nama } = el.dataset;
  const rows = await api(`/api/laporan/detail?pos=${pos}&key=${encodeURIComponent(key)}&dari=${$("#lr-dari").value}&sampai=${$("#lr-sampai").value}`);
  const total = rows.reduce((s, r) => s + (r.jumlah || 0), 0);
  dialog(`${POS_JUDUL[pos]}: ${nama}`,
    tabel([
      { label: "Tanggal", key: "tanggal" },
      { label: "Keterangan", key: "keterangan" },
      { label: "Rumus", key: "rumus" },
      { label: "Jumlah", num: true, get: (r) => (r.jumlah === null ? "" : rp(r.jumlah)) },
    ], rows) + `<p class="total-form">Total: <b>${rp(total)}</b></p>`);
});

$("#lr-tampil").addEventListener("click", muatLaporan);
loaders.laporan = muatLaporan;

// ---------- form item dinamis ----------
function itemTable(form, buatBaris, hitung) {
  const tbody = $("table.items tbody", form);
  const tambah = (data) => {
    const tr = document.createElement("tr");
    tr.innerHTML = buatBaris(data || {});
    tbody.appendChild(tr);
    hitung();
  };
  $(".tambah-item", form).addEventListener("click", () => tambah());
  tbody.addEventListener("input", hitung);
  tbody.addEventListener("change", (e) => {
    if (e.target.name === "produk_id") {
      const p = PRODUK.find((x) => x.id == e.target.value);
      const harga = $('[name="harga"]', e.target.closest("tr"));
      if (p && harga) harga.value = p.harga_jual;
    }
    hitung();
  });
  tbody.addEventListener("click", (e) => {
    if (e.target.classList.contains("hapus-baris")) {
      e.target.closest("tr").remove();
      hitung();
    }
  });
  return { tambah, reset: () => { tbody.innerHTML = ""; }, baris: () => [...tbody.rows] };
}

// ---------- penjualan ----------
const fPj = $("#f-penjualan");
const pjItems = itemTable(
  fPj,
  (d) => `<td><select name="produk_id" required><option value="">- pilih -</option>${PRODUK.map((p) => `<option value="${p.id}" ${p.id == d.produk_id ? "selected" : ""}>${esc(p.nama)}</option>`).join("")}</select></td>
    <td><input type="number" name="qty" step="any" min="0" value="${d.qty ?? 1}" required></td>
    <td><input type="number" name="harga" step="any" min="0" value="${d.harga ?? ""}" required></td>
    <td class="num sub">Rp0</td><td><button type="button" class="link hapus-baris">✕</button></td>`,
  () => {
    let t = 0;
    for (const tr of pjItems.baris()) {
      const s = ($('[name="qty"]', tr).value || 0) * ($('[name="harga"]', tr).value || 0);
      $(".sub", tr).textContent = rp(s);
      t += s;
    }
    $("#pj-total").textContent = rp(t);
  }
);

fPj.addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = formData(fPj);
  const items = pjItems.baris().map((tr) => ({
    produk_id: +$('[name="produk_id"]', tr).value,
    qty: +$('[name="qty"]', tr).value,
    harga: +$('[name="harga"]', tr).value,
  }));
  if (!items.length) return toast("Tambahkan minimal 1 item.");
  await edPj.kirim("/api/penjualan", { tanggal: d.tanggal, pemesan: d.pemesan, metode: d.metode, catatan: d.catatan, items });
  const tgl = d.tanggal;
  fPj.reset();
  fPj.tanggal.value = tgl;
  edPj.selesai();
  pjItems.reset();
  pjItems.tambah();
  await muatPenjualan();
});

const edPj = editor(fPj, () => { pjItems.reset(); pjItems.tambah(); });
let DATA_PJ = [];
window.editPenjualan = (id) => {
  const r = DATA_PJ.find((x) => x.id === id);
  fPj.reset();
  for (const k of ["tanggal", "pemesan", "metode", "catatan"]) fPj[k].value = r[k] ?? "";
  pjItems.reset();
  r.items.forEach((i) => pjItems.tambah(i));
  edPj.mulai(id, `Edit penjualan #${id}`);
};

async function muatPenjualan() {
  if (!pjItems.baris().length) pjItems.tambah();
  const data = (DATA_PJ = await api("/api/penjualan"));
  $("#list-penjualan").innerHTML = tabel(
    [
      { label: "Tanggal", key: "tanggal" },
      { label: "Pemesan", key: "pemesan" },
      { label: "Pesanan", html: (r) => r.items.map((i) => `${esc(i.produk)} × ${num(i.qty)}`).join("<br>") },
      { label: "Metode", key: "metode" },
      { label: "Total", num: true, get: (r) => rp(r.total) },
      { label: "HPP", num: true, get: (r) => rp(r.hpp) },
    ],
    data,
    (r) => tombolEdit("editPenjualan", r.id) + `<button class="link" onclick="hapus('/api/penjualan/${r.id}', muatPenjualan)">Hapus</button>`
  );
}
window.muatPenjualan = muatPenjualan;
loaders.penjualan = muatPenjualan;

// ---------- pembelian ----------
const fPb = $("#f-pembelian");
fPb.bahan_id.addEventListener("change", () => {
  const b = BAHAN.find((x) => x.id == fPb.bahan_id.value);
  $("#pb-satuan").textContent = b ? `Qty dalam ${b.satuan}. Harga rata-rata saat ini ${rp(b.harga_rata)}/${b.satuan}, stok ${num(b.stok)} ${b.satuan}.` : "";
});
fPb.addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = formData(fPb);
  await edPb.kirim("/api/pembelian", { ...d, bahan_id: +d.bahan_id, qty: +d.qty, total: +d.total });
  const tgl = d.tanggal;
  fPb.reset();
  fPb.tanggal.value = tgl;
  edPb.selesai();
  $("#pb-satuan").textContent = "";
  await muatMaster();
  await muatPembelian();
});

const edPb = editor(fPb, () => ($("#pb-satuan").textContent = ""));
let DATA_PB = [];
window.editPembelian = (id) => {
  const r = DATA_PB.find((x) => x.id === id);
  for (const k of ["tanggal", "bahan_id", "qty", "total", "pemasok", "catatan"]) fPb[k].value = r[k] ?? "";
  fPb.bahan_id.dispatchEvent(new Event("change"));
  edPb.mulai(id, `Edit pembelian #${id}`);
};

async function muatPembelian() {
  const data = (DATA_PB = await api("/api/pembelian"));
  $("#list-pembelian").innerHTML = tabel(
    [
      { label: "Tanggal", key: "tanggal" },
      { label: "Bahan", key: "bahan" },
      { label: "Qty", num: true, get: (r) => `${num(r.qty)} ${r.satuan}` },
      { label: "Total", num: true, get: (r) => rp(r.total) },
      { label: "Harga/satuan", num: true, get: (r) => rp(r.harga_satuan) },
      { label: "Pemasok", key: "pemasok" },
    ],
    data,
    (r) => tombolEdit("editPembelian", r.id) + `<button class="link" onclick="hapus('/api/pembelian/${r.id}', muatPembelian)">Hapus</button>`
  );
}
window.muatPembelian = muatPembelian;
loaders.pembelian = muatPembelian;

// ---------- foto struk ----------
// Foto diperkecil di browser lalu dikirim sekali untuk dibaca; tidak disimpan di server maupun browser.
function kecilkanFoto(file, sisiMaks = 1800) {
  return new Promise((ok, gagal) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const k = Math.min(1, sisiMaks / Math.max(img.width, img.height));
      const cv = document.createElement("canvas");
      cv.width = Math.round(img.width * k);
      cv.height = Math.round(img.height * k);
      cv.getContext("2d").drawImage(img, 0, 0, cv.width, cv.height);
      URL.revokeObjectURL(url);
      cv.toBlob((b) => (b ? ok(b) : gagal(new Error("Gagal memproses gambar."))), "image/jpeg", 0.85);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      gagal(new Error("File ini bukan gambar yang bisa dibuka."));
    };
    img.src = url;
  });
}

let DRAF_STRUK = [];

$("#struk-baca").addEventListener("click", async () => {
  const file = $("#struk-file").files[0];
  const status = $("#struk-status"), tombol = $("#struk-baca");
  if (!file) return toast("Pilih foto struk dulu");
  tombol.disabled = true;
  status.textContent = "Membaca struk, mohon tunggu...";
  try {
    const blob = await kecilkanFoto(file);
    const res = await fetch("/api/struk/baca", { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || res.statusText);
    await muatMaster();
    tampilkanDraf(data);
    status.textContent = "Periksa hasil di bawah, perbaiki yang salah, lalu simpan. Foto tidak disimpan.";
  } catch (e) {
    status.textContent = "Gagal: " + e.message;
  } finally {
    tombol.disabled = false;
    $("#struk-file").value = "";
  }
});

function tampilkanDraf(d) {
  // qty_bahan 0 = OCR tak bisa menghitung satuan: pakai jumlah di struk sebagai perkiraan awal (ditandai auto).
  DRAF_STRUK = d.item.map((it) => ({ ...it, auto: !it.qty_bahan, qty: it.qty_bahan || it.jumlah || "" }));
  const opsi = (id) =>
    '<option value="">- pilih bahan -</option><option value="baru">+ Bahan baru...</option>' +
    BAHAN.map((b) => `<option value="${b.id}"${b.id === id ? " selected" : ""}>${esc(b.nama)} (${esc(b.satuan)})</option>`).join("");
  const baris = DRAF_STRUK.map(
    (it, i) => `<tr data-i="${i}">
      <td><div class="nama-struk">Di struk: ${esc(it.nama_struk)} (${num(it.jumlah)}x)</div>
        <select name="bahan">${opsi(it.bahan_id)}</select>
        <div class="baru" hidden>
          <input name="nama_baru" placeholder="Nama bahan baru" value="${esc(it.nama_struk)}">
          <input name="satuan_baru" placeholder="Satuan (gram, pcs, ml...)">
        </div></td>
      <td><input type="number" step="any" min="0" name="qty" value="${it.qty}" placeholder="Qty"${it.auto ? " data-auto" : ""}></td>
      <td><input type="number" step="any" min="0" name="total" value="${it.total}"></td>
      <td class="num"><button type="button" class="link" data-hapus>Buang</button></td>
    </tr>`
  ).join("");
  const box = $("#struk-review");
  box.hidden = false;
  box.innerHTML = `
    <div class="grid">
      <label>Tanggal <input type="date" name="tanggal" value="${esc(d.tanggal || today())}"></label>
      <label>Pemasok <input name="pemasok" value="${esc(d.pemasok)}"></label>
    </div>
    ${d.item.length ? `<div class="tabel-wrap"><table class="items"><thead><tr><th>Barang</th><th>Qty (satuan bahan)</th><th>Total (Rp)</th><th></th></tr></thead><tbody>${baris}</tbody></table></div>` : '<p class="hint">Tidak ada barang yang terbaca. Coba foto yang lebih jelas.</p>'}
    <p class="hint">Qty yang kosong/perkiraan diisi dari jumlah di struk: sesuaikan dengan satuan bahan (mis. 2 bungkus @500 g = 1000 gram).</p>
    <p class="hint" id="struk-jumlah"></p>
    <button type="button" id="struk-simpan">Simpan semua</button>
    <button type="button" class="secondary" id="struk-batal">Batal</button>`;
  hitungStruk();
  $("#struk-batal").onclick = () => {
    box.hidden = true;
    box.innerHTML = "";
  };
  $("#struk-simpan").onclick = simpanStruk;
}

{
  const box = $("#struk-review");
  box.addEventListener("input", (e) => {
    if (e.target.name === "qty") delete e.target.dataset.auto; // sudah diedit pengguna
    hitungStruk();
  });
  box.addEventListener("change", (e) => {
    if (e.target.name !== "bahan") return;
    const tr = e.target.closest("tr");
    $(".baru", tr).hidden = e.target.value !== "baru";
    // Pilih bahan & qty masih kosong/perkiraan: isi dari jumlah di struk (sesuaikan dengan satuan bahan).
    const qty = $('[name="qty"]', tr), it = DRAF_STRUK[+tr.dataset.i];
    if (e.target.value && it && (!qty.value || "auto" in qty.dataset)) {
      qty.value = it.jumlah || "";
      qty.dataset.auto = "";
    }
  });
  box.addEventListener("click", (e) => {
    if (!e.target.matches("[data-hapus]")) return;
    e.target.closest("tr").remove();
    hitungStruk();
  });
}

function hitungStruk() {
  const trs = [...document.querySelectorAll("#struk-review tbody tr")];
  const total = trs.reduce((a, tr) => a + (+$('[name="total"]', tr).value || 0), 0);
  const el = $("#struk-jumlah");
  if (el) el.textContent = `${trs.length} barang, jumlah ${rp(total)}. Cocokkan dengan total di struk.`;
}

async function simpanStruk() {
  const box = $("#struk-review");
  const trs = [...box.querySelectorAll("tbody tr")];
  if (!trs.length) return toast("Tidak ada barang untuk disimpan");
  const items = [];
  for (const tr of trs) {
    const pilih = $('[name="bahan"]', tr).value;
    const qty = +$('[name="qty"]', tr).value, total = +$('[name="total"]', tr).value;
    if (!pilih) return toast("Ada barang yang bahannya belum dipilih");
    if (!(qty > 0)) return toast("Ada barang yang qty-nya belum diisi");
    const it = { qty, total };
    if (pilih === "baru") {
      const nama = $('[name="nama_baru"]', tr).value.trim(), satuan = $('[name="satuan_baru"]', tr).value.trim();
      if (!nama || !satuan) return toast("Isi nama dan satuan untuk bahan baru");
      it.bahan_baru = { nama, satuan };
    } else it.bahan_id = +pilih;
    items.push(it);
  }
  await api("/api/pembelian/banyak", {
    method: "POST",
    body: { tanggal: $('[name="tanggal"]', box).value, pemasok: $('[name="pemasok"]', box).value, catatan: "", items },
  });
  toast(`${items.length} pembelian tersimpan`);
  box.hidden = true;
  box.innerHTML = "";
  $("#struk-status").textContent = "Tersimpan.";
  await muatMaster();
  await muatPembelian();
}

// ---------- beban ----------
const fBb = $("#f-beban");
fBb.addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = formData(fBb);
  await edBb.kirim("/api/beban", { ...d, jumlah: +d.jumlah });
  const tgl = d.tanggal;
  fBb.reset();
  fBb.tanggal.value = tgl;
  edBb.selesai();
  await muatBeban();
});

const edBb = editor(fBb);
let DATA_BB = [];
window.editBeban = (id) => {
  const r = DATA_BB.find((x) => x.id === id);
  for (const k of ["tanggal", "kategori", "jumlah", "catatan"]) fBb[k].value = r[k] ?? "";
  edBb.mulai(id, `Edit beban #${id}`);
};

async function muatBeban() {
  const [data, kat] = await Promise.all([api("/api/beban"), api("/api/kategori-beban")]);
  DATA_BB = data;
  $("#dl-kategori").innerHTML = kat.map((k) => `<option value="${esc(k)}">`).join("");
  $("#list-beban").innerHTML = tabel(
    [
      { label: "Tanggal", key: "tanggal" },
      { label: "Kategori", key: "kategori" },
      { label: "Jumlah", num: true, get: (r) => rp(r.jumlah) },
      { label: "Catatan", key: "catatan" },
    ],
    data,
    (r) => tombolEdit("editBeban", r.id) + `<button class="link" onclick="hapus('/api/beban/${r.id}', muatBeban)">Hapus</button>`
  );
}
window.muatBeban = muatBeban;
loaders.beban = muatBeban;

// ---------- bahan ----------
const fBh = $("#f-bahan");
fBh.addEventListener("submit", async (e) => {
  e.preventDefault();
  await api("/api/bahan", { method: "POST", body: formData(fBh) });
  toast("Bahan tersimpan");
  fBh.reset();
  await muatBahan();
});

async function muatBahan() {
  await muatMaster();
  const totalNilai = BAHAN.reduce((s, b) => s + b.nilai, 0);
  $("#list-bahan").innerHTML =
    tabel(
      [
        { label: "Bahan", key: "nama" },
        { label: "Stok", num: true, html: (r) => `<span class="${r.stok < 0 ? "neg" : ""}">${num(r.stok)} ${esc(r.satuan)}</span>` },
        { label: "Harga rata-rata", num: true, get: (r) => `${rp(r.harga_rata)}/${r.satuan}` },
        { label: "Nilai persediaan", num: true, get: (r) => rp(r.nilai) },
      ],
      BAHAN,
      (r) => `<button class="link biasa" onclick="lihatMutasi(${r.id})">Riwayat</button><button class="link" onclick="hapus('/api/bahan/${r.id}', muatBahan)">Hapus</button>`
    ) + `<p class="total-form">Total nilai persediaan: <b>${rp(totalNilai)}</b> <span class="hint">(= jumlah stok × harga rata-rata)</span></p>`;
}
window.muatBahan = muatBahan;
loaders.bahan = muatBahan;

window.lihatMutasi = async (id) => {
  const b = BAHAN.find((x) => x.id === id);
  const data = await api(`/api/bahan/${id}/mutasi`);
  const JENIS = { beli: "Pembelian", pakai: "Dipakai (penjualan)", opname: "Stok opname" };
  dialog(`Riwayat stok: ${b.nama}`,
    tabel(
      [
        { label: "Tanggal", key: "tanggal" },
        { label: "Jenis", get: (r) => JENIS[r.jenis] },
        { label: "Ref", key: "ref" },
        { label: "Qty", num: true, get: (r) => `${r.qty > 0 ? "+" : ""}${num(r.qty)}` },
        { label: "Nilai", num: true, get: (r) => rp(r.nilai) },
        { label: "Stok setelah", num: true, get: (r) => num(r.stok_setelah) },
        { label: "Harga rata setelah", num: true, get: (r) => rp(r.harga_rata_setelah) },
      ],
      data
    ) + `<p class="hint">Harga rata baru = (stok lama × harga rata lama + total pembelian) ÷ (stok lama + qty beli)</p>`);
};

// ---------- produk ----------
const fPr = $("#f-produk");
const prItems = itemTable(
  fPr,
  (d) => `<td><select name="bahan_id" required>${'<option value="">- pilih -</option>' + BAHAN.map((b) => `<option value="${b.id}" ${b.id == d.bahan_id ? "selected" : ""}>${esc(b.nama)} (${esc(b.satuan)})</option>`).join("")}</select></td>
    <td><input type="number" name="qty" step="any" min="0" value="${d.qty ?? ""}" required></td>
    <td class="num sub">Rp0</td><td><button type="button" class="link hapus-baris">✕</button></td>`,
  () => {
    let t = 0;
    for (const tr of prItems.baris()) {
      const b = BAHAN.find((x) => x.id == $('[name="bahan_id"]', tr).value);
      const s = b ? b.harga_rata * ($('[name="qty"]', tr).value || 0) : 0;
      $(".sub", tr).textContent = rp(s);
      t += s;
    }
    $("#pr-hpp").textContent = rp(t);
  }
);

function resetProduk() {
  fPr.reset();
  fPr.pid.value = "";
  prItems.reset();
  $("#pr-judul").textContent = "Tambah produk";
  $("#pr-batal").hidden = true;
  $("#pr-hpp").textContent = "Rp0";
}
$("#pr-batal").addEventListener("click", resetProduk);

fPr.addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = formData(fPr);
  const resep = prItems.baris().map((tr) => ({ bahan_id: +$('[name="bahan_id"]', tr).value, qty: +$('[name="qty"]', tr).value }));
  const body = { nama: d.nama, harga_jual: +d.harga_jual, resep };
  if (d.pid) await api(`/api/produk/${d.pid}`, { method: "PUT", body });
  else await api("/api/produk", { method: "POST", body });
  toast("Produk tersimpan");
  resetProduk();
  await muatProduk();
});

window.editProduk = (id) => {
  const p = PRODUK.find((x) => x.id === id);
  resetProduk();
  fPr.pid.value = p.id;
  fPr.nama.value = p.nama;
  fPr.harga_jual.value = p.harga_jual;
  p.resep.forEach((r) => prItems.tambah(r));
  $("#pr-judul").textContent = "Edit produk: " + p.nama;
  $("#pr-batal").hidden = false;
  fPr.scrollIntoView({ behavior: "smooth" });
};

async function muatProduk() {
  await muatMaster();
  $("#list-produk").innerHTML = tabel(
    [
      { label: "Produk", key: "nama" },
      { label: "Harga jual", num: true, get: (r) => rp(r.harga_jual) },
      { label: "Resep", html: (r) => r.resep.map((x) => `${esc(x.nama)} ${num(x.qty)} ${esc(x.satuan)}`).join("<br>") || '<span class="neg">belum ada</span>' },
      { label: "HPP/unit", num: true, get: (r) => rp(r.hpp_saat_ini) },
      { label: "Margin", num: true, get: (r) => (r.harga_jual ? (((r.harga_jual - r.hpp_saat_ini) / r.harga_jual) * 100).toFixed(1) + "%" : "-") },
    ],
    PRODUK,
    (r) => `<button class="link biasa" onclick="editProduk(${r.id})">Edit</button><button class="link" onclick="hapus('/api/produk/${r.id}', muatProduk)">Hapus</button>`
  );
}
window.muatProduk = muatProduk;
loaders.produk = muatProduk;

// ---------- opname ----------
const fOp = $("#f-opname");
fOp.addEventListener("submit", async (e) => {
  e.preventDefault();
  const d = formData(fOp);
  await edOp.kirim("/api/opname", { ...d, bahan_id: +d.bahan_id, qty_aktual: +d.qty_aktual });
  const tgl = d.tanggal;
  fOp.reset();
  fOp.tanggal.value = tgl;
  edOp.selesai();
  await muatOpname();
});

const edOp = editor(fOp);
let DATA_OP = [];
window.editOpname = (id) => {
  const r = DATA_OP.find((x) => x.id === id);
  for (const k of ["tanggal", "bahan_id", "qty_aktual", "catatan"]) fOp[k].value = r[k] ?? "";
  edOp.mulai(id, `Edit stok opname #${id}`);
};

async function muatOpname() {
  const data = (DATA_OP = await api("/api/opname"));
  $("#list-opname").innerHTML = tabel(
    [
      { label: "Tanggal", key: "tanggal" },
      { label: "Bahan", key: "bahan" },
      { label: "Stok sistem", num: true, get: (r) => `${num(r.qty_sistem)} ${r.satuan}` },
      { label: "Aktual", num: true, get: (r) => `${num(r.qty_aktual)} ${r.satuan}` },
      { label: "Selisih", num: true, html: (r) => `<span class="${r.selisih < 0 ? "neg" : ""}">${num(r.selisih)}</span>` },
      { label: "Nilai selisih", num: true, get: (r) => rp(r.nilai) },
    ],
    data,
    (r) => tombolEdit("editOpname", r.id) + `<button class="link" onclick="hapus('/api/opname/${r.id}', muatOpname)">Hapus</button>`
  );
}
window.muatOpname = muatOpname;
loaders.opname = muatOpname;

// ---------- init ----------
(async function init() {
  const t = today();
  for (const f of [fPj, fPb, fBb, fOp]) f.tanggal.value = t;
  $("#lr-dari").value = t.slice(0, 8) + "01";
  $("#lr-sampai").value = t;
  await muatMaster();
  await muatLaporan();
})();
