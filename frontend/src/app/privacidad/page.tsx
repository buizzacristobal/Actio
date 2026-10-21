import type { Metadata } from "next";
import { Footer } from "@/components/landing/Footer";
import { Header } from "@/components/landing/Header";

export const metadata: Metadata = { title: "Privacidad y tratamiento de datos — LegalTech Chile" };

const ITEMS: [string, string][] = [
  ["Qué datos se procesan", "Los documentos que usted sube o pega (pagarés, facturas), los datos de las partes que contienen y los datos del abogado que ingresa en el formulario."],
  ["Dónde se procesan", "La extracción envía el texto, o la imagen para OCR, al proveedor de IA configurado en el servidor. El cálculo de la liquidación y la generación del documento ocurren en el servidor de esta aplicación."],
  ["Qué se almacena", "Nada. Los documentos y los resultados viven solo en memoria mientras dura la solicitud. Los registros de acceso guardan método, ruta, código de respuesta y duración, nunca el contenido de los documentos ni parámetros de consulta."],
  ["Borradores locales", "Si usted pulsa «Guardar borrador», los datos del caso se guardan únicamente en el almacenamiento local de su navegador. Puede borrarlos en cualquier momento desde la aplicación."],
  ["Cookies y analítica", "El sitio no usa cookies de seguimiento ni herramientas de analítica."],
  ["Su proveedor de IA", "El tratamiento por parte del proveedor de IA se rige por sus propios términos. Verifique su política de retención antes de enviar datos reales de clientes."],
];

export default function Privacy() {
  return (
    <>
      <Header />
      <main className="container-x max-w-3xl py-16">
        <p className="eyebrow">Privacidad</p>
        <h1 className="mt-3 text-4xl font-semibold">Tratamiento de datos</h1>
        <dl className="mt-10 space-y-8">
          {ITEMS.map(([t, d]) => (
            <div key={t}>
              <dt className="font-serif text-xl font-semibold">{t}</dt>
              <dd className="mt-2 text-sm leading-relaxed text-ink-700">{d}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-12 rounded-lg border border-gold-200 bg-gold-100/60 p-4 text-sm">
          <strong>Documento informativo del prototipo.</strong> Describe el comportamiento técnico del software. No es una política de
          privacidad legal: antes de un uso comercial debe ser revisado por un asesor y completarse con la identidad del responsable
          del tratamiento y sus datos de contacto, conforme a la Ley 21.719.
        </p>
      </main>
      <Footer />
    </>
  );
}
