const CFG = {
  SHEET_ID: 'SPREADSHEET_ID', // Digantikan otomatis dari Script Properties
  EDITORS: 'EDITOR_EMAILS',
  TZ: 'Asia/Jakarta'
};

// Daftar Akun Editor (Username & Password)
const USERS = {
  "admin": "admin123",
  "staf": "staf123",
  "kasir": "kasir123"
};

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('PSM Toko - Sales Dashboard')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function getData() {
  const ss = SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty(CFG.SHEET_ID));
  return {
    periods: table_(ss, 'PERIODE'),
    items: table_(ss, 'SALES_ITEM'),
    personil: table_(ss, 'SALES_PERSONIL'),
    masterItems: table_(ss, 'MASTER_ITEM'),
    masterPersons: table_(ss, 'MASTER_PERSONIL'),
    now: new Date().toISOString()
  };
}

// Fungsi Verifikasi Login
function checkLogin(username, password) {
  if (USERS[username] && USERS[username] === password) {
    return { success: true, user: username };
  } else {
    throw new Error('Username atau Password salah!');
  }
}

// Simpan Data Sales Item (Dengan Cek Login)
function saveSalesItemWithAuth(auth, x) {
  checkLogin(auth.username, auth.password);
  return save_(x, 'SALES_ITEM', ['period_id', 'item_id', 'actual_qty']);
}

// Simpan Data Sales Personil (Dengan Cek Login)
function saveSalesPersonilWithAuth(auth, x) {
  checkLogin(auth.username, auth.password);
  return save_(x, 'SALES_PERSONIL', ['period_id', 'item_id', 'person_id', 'actual_qty']);
}

function save_(x, name, req) {
  req.forEach(k => {
    if (x[k] === undefined || x[k] === '') throw Error(k + ' wajib diisi');
  });
  if (Number(x.actual_qty) < 0 || !isFinite(Number(x.actual_qty))) throw Error('Qty tidak valid');

  const ss = SpreadsheetApp.openById(PropertiesService.getScriptProperties().getProperty(CFG.SHEET_ID));
  const sh = ss.getSheetByName(name);
  const v = sh.getDataRange().getValues();
  const h = v.shift();
  const ix = {};
  h.forEach((z, i) => ix[z] = i);

  const match = v.findIndex(r => 
    String(r[ix.period_id]) === String(x.period_id) && 
    String(r[ix.item_id]) === String(x.item_id) && 
    (!ix.person_id || String(r[ix.person_id]) === String(x.person_id))
  );

  if (match >= 0) {
    sh.getRange(match + 2, ix.actual_qty + 1).setValue(Number(x.actual_qty));
    if (ix.updated_at !== undefined) sh.getRange(match + 2, ix.updated_at + 1).setValue(new Date());
  } else {
    const mi = table_(ss, 'MASTER_ITEM').find(r => String(r.item_id) === String(x.item_id));
    const mp = ix.person_id ? table_(ss, 'MASTER_PERSONIL').find(r => String(r.person_id) === String(x.person_id)) : null;
    
    if (!mi || (ix.person_id && !mp)) throw Error('Master ID tidak valid');

    if (ix.person_id) {
      sh.appendRow([Utilities.getUuid(), x.period_id, x.item_id, mi.item_name, x.person_id, mp.person_name, Number(x.actual_qty), new Date()]);
    } else {
      sh.appendRow([Utilities.getUuid(), x.period_id, x.item_id, mi.item_name, 0, Number(x.actual_qty), new Date()]);
    }
  }
  return getData();
}

function table_(ss, n) {
  const s = ss.getSheetByName(n);
  if (!s) return [];
  const v = s.getDataRange().getValues();
  if (v.length < 2) return [];
  const h = v.shift();
  return v
    .filter(r => r.some(x => x !== '' && x !== null))
    .map(r => Object.fromEntries(h.map((k, i) => [
      k, 
      r[i] instanceof Date ? r[i].toISOString() : (isNaN(r[i]) || r[i] === '' ? r[i] : Number(r[i]))
    ])));
}
