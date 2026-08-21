// T5: sonda de conformance do SDK TypeScript oficial (@x402/mcp) — shape do
// payment-required (N1/N2) + constantes (_meta keys N4/N5, código de erro NC-3).
// Roda OFFLINE: resource server falso, nenhum facilitator.
// Uso: node check.mjs   (requer `npm install @x402/mcp` no diretório indicado por
// MESA_TS_CHECK_DIR — por padrão C:\dev\mesa-ts-check, fora do OneDrive)
import { createRequire } from "node:module";

const dir = process.env.MESA_TS_CHECK_DIR || "C:\\dev\\mesa-ts-check";
const require = createRequire(dir + "\\package.json");
const m = require("@x402/mcp");

const fakeScheme = {
  scheme: "exact",
  defaultAssetTransferMethod: "eip3009",
  paymentFlows: { eip3009: { default: "settle-after", supported: ["settle-after"] } },
};
const rs = {
  getRegisteredScheme: () => fakeScheme,
  findMatchingRequirements: () => null,
  createPaymentRequiredResponse: (accepts, resource, error) => ({
    x402Version: 2, accepts, error, resource,
  }),
};
const accepts = [{
  scheme: "exact", network: "eip155:84532",
  asset: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
  amount: "10000", payTo: "0xe79B79edEF18A726c989da6546Ba4fa23a8F12d8",
  maxTimeoutSeconds: 300,
}];

const paid = m.createPaymentWrapper(rs, { accepts });
const wrapped = paid(async () => ({ content: [{ type: "text", text: "ok" }] }));
const r = await wrapped({ pergunta: "conformance" }, { _meta: undefined });

let textoJsonValido = false;
try { JSON.parse(r.content[0].text); textoJsonValido = true; } catch {}

import { readFileSync } from "node:fs";
const pkg = JSON.parse(readFileSync(dir + "\\node_modules\\@x402\\mcp\\package.json", "utf8"));

console.log(JSON.stringify({
  versao: pkg.version,
  n1_is_error_in_band: r.isError === true,
  n2_structured_content: r.structuredContent !== undefined,
  n2_content_text_json: textoJsonValido,
  n4_meta_key: m.MCP_PAYMENT_META_KEY,
  n5_meta_response_key: m.MCP_PAYMENT_RESPONSE_META_KEY,
  nc3_codigo_erro: m.MCP_PAYMENT_REQUIRED_CODE,
}));
