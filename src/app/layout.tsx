import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Nexus-Alpha — Córtex Audit",
  description: "Monitoramento e auditoria da IA autônoma de grafos",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" className="bg-slate-950 scroll-smooth">
      <body className="antialiased selection:bg-violet-500/30 selection:text-violet-200">
        {children}
      </body>
    </html>
  );
}
