import type { Metadata } from "next"
import { GeistSans } from "geist/font/sans"
import { GeistMono } from "geist/font/mono"

import { Sidebar } from "@/components/layout/sidebar"
import { ThemeProvider } from "@/components/layout/theme-provider"
import "./globals.css"

export const metadata: Metadata = {
  title: "Nexus",
  description: "The AI control plane for enterprise data engineering",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <ThemeProvider>
          <div className="flex h-dvh overflow-hidden">
            <Sidebar />
            <main className="flex min-w-0 flex-1 flex-col">{children}</main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  )
}
