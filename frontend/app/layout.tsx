import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "react-hot-toast";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
  variable: "--font-inter",
});
const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Sultan Clip",
  description: "Turn long videos into ready-to-post clips",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: `
          (function() {
            try {
              var t = localStorage.getItem('theme') || 'dark';
              document.documentElement.setAttribute('data-theme', t);
            } catch(e) {
              document.documentElement.setAttribute('data-theme', 'dark');
            }
          })();
        `}} />
      </head>
      <body className={`${geist.variable} ${geistMono.variable}`}>
        {children}
        <Toaster
          position="top-center"
          gutter={12}
          toastOptions={{
            duration: 3600,
            style: {
              background: "var(--bg-soft)",
              border: "1px solid var(--border)",
              borderRadius: "12px",
              boxShadow: "var(--shadow-md)",
              color: "var(--text-primary)",
              fontSize: "14px",
              fontWeight: 500,
              padding: "12px 14px",
            },
            success: {
              iconTheme: {
                primary: "var(--success)",
                secondary: "var(--bg-soft)",
              },
            },
            error: {
              iconTheme: {
                primary: "var(--danger)",
                secondary: "var(--bg-soft)",
              },
            },
          }}
        />
      </body>
    </html>
  );
}
