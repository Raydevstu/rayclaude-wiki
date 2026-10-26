// React Imports
import type { ReactNode } from 'react'

// Next Imports
import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'

// Third-party Imports
import { NuqsAdapter } from 'nuqs/adapters/next/app'

// Component Imports
import Providers from '@/components/Providers'
import { TooltipProvider } from '@/components/ui/tooltip'

// Util Imports
import { cn } from '@/lib/utils'

// Style Imports
import './globals.css'
import ScrollToTop from '@/components/layout/ScrollToTop'

import DownloadButton from '@/components/layout/Download'

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin']
})

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin']
})

export const metadata: Metadata = {
  title: 'AdminCN - Free Shadcn Admin Dashboard Template',
  description:
    'Build modern admin dashboards faster with AdminCN Free. A free shadcn admin dashboard template built with Tailwind CSS, featuring responsive layouts and essential pages.',
  metadataBase: new URL(`${process.env.NEXT_PUBLIC_APP_URL ?? 'http://localhost:3000'}`),
  openGraph: {
    title: 'AdminCN - Free Shadcn Admin Dashboard Template',
    description:
      'Build modern admin dashboards faster with AdminCN Free. A free shadcn admin dashboard template built with Tailwind CSS, featuring responsive layouts and essential pages.',
    type: 'website',
    siteName: 'AdminCN',
    url: process.env.NEXT_PUBLIC_APP_URL,
    images: [
      {
        url: '/images/og-image.png',
        type: 'image/png',
        width: 1200,
        height: 630,
        alt: 'AdminCN - Free Shadcn Admin Dashboard Template'
      }
    ]
  },
  twitter: {
    card: 'summary_large_image',
    title: 'AdminCN - Free Shadcn Admin Dashboard Template',
    description:
      'Build modern admin dashboards faster with AdminCN Free. A free shadcn admin dashboard template built with Tailwind CSS, featuring responsive layouts and essential pages.'
  }
}

const RootLayout = ({ children }: Readonly<{ children: ReactNode }>) => {
  return (
    <html
      lang='en'
      className={cn(geistSans.variable, geistMono.variable, 'flex min-h-full w-full antialiased')}
      data-scroll-behavior='smooth'
      suppressHydrationWarning
    >
      <body className='flex min-h-full w-full flex-auto flex-col'>
        <NuqsAdapter>
          <Providers sidebarDefaultOpen={true}>
            <TooltipProvider>{children}</TooltipProvider>
          </Providers>
        </NuqsAdapter>

        <ScrollToTop />

        <DownloadButton />
      </body>
    </html>
  )
}

export default RootLayout
