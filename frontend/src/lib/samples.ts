import type { Instrument } from "./types";
import samples from "./samples.json";

export const SAMPLE_PAGARE_TEXT = `PAGARÉ
Lugar y fecha: Santiago, 20 de enero de 2024.
Debo y pagaré a Banco Ejemplo SpA, RUT 76.086.428-5, la suma de $1.000.000 (un millón de pesos)
el día 20 de marzo de 2024. Interés convencional: 24% anual. Firma autorizada ante notario.
Deudor: Juan Pérez González, RUT 12.345.678-5, domiciliado en Los Olmos 123, Ñuñoa.`;

export const SAMPLE_FACTURA_TEXT = `FACTURA ELECTRÓNICA N° 1234
Emisor: Banco Ejemplo SpA, RUT 76.086.428-5. Receptor: Juan Pérez González, RUT 12.345.678-5.
Fecha de emisión: 20-01-2024. Vencimiento: 20-03-2024.
Neto $1.000.000  IVA $190.000  Total $1.190.000. Acuse de recibo: SI.`;

export const SAMPLE_PAGARE = samples.pagare as Instrument;
export const SAMPLE_FACTURA = samples.factura as Instrument;
