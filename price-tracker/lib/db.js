// Armazenamento em arquivo JSON com escrita atômica (sem dependências nativas).
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

export const DEFAULT_SETTINGS = {
  checkIntervalMinutes: 60,
  couponIntervalHours: 6,
  defaultDropPercent: 3,
  ntfyServer: "https://ntfy.sh",
  ntfyTopic: "",
  telegramBotToken: "",
  telegramChatId: "",
  webhookUrl: "",
  couponSources: [
    "https://www.cuponomia.com.br/desconto/{slug}",
    "https://www.meliuz.com.br/desconto/cupom-{slug}",
    "https://www.pelando.com.br/cupons-de-descontos/{slug}",
  ],
};

export const newId = () => crypto.randomBytes(6).toString("hex");

export class Store {
  constructor(file) {
    this.file = file;
    this.data = { products: [], coupons: [], notifications: [], settings: { ...DEFAULT_SETTINGS } };
    if (file && fs.existsSync(file)) {
      const loaded = JSON.parse(fs.readFileSync(file, "utf8"));
      this.data = { ...this.data, ...loaded, settings: { ...DEFAULT_SETTINGS, ...loaded.settings } };
    }
    this.timer = null;
  }

  get products() { return this.data.products; }
  get coupons() { return this.data.coupons; }
  get settings() { return this.data.settings; }
  get notifications() { return this.data.notifications; }

  product(id) { return this.data.products.find((p) => p.id === id); }

  /** Agenda gravação (agrupa várias alterações seguidas). */
  save() {
    if (!this.file) return;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.flush(), 200);
  }

  flush() {
    if (!this.file) return;
    clearTimeout(this.timer);
    fs.mkdirSync(path.dirname(this.file), { recursive: true });
    const tmp = `${this.file}.${process.pid}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(this.data, null, 1));
    fs.renameSync(tmp, this.file);
  }

  logNotification(entry) {
    this.data.notifications.unshift({ id: newId(), at: new Date().toISOString(), ...entry });
    this.data.notifications.length = Math.min(this.data.notifications.length, 300);
    this.save();
  }
}
