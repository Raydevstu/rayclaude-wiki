'use client'

// Next Imports
import { Fragment } from 'react'

import { usePathname } from 'next/navigation'

// Third-party Imports
import { LanguagesIcon } from 'lucide-react'

// Component Imports
import LanguageDropdown from '@/components/shared/LanguageDropdown'
import ModeToggle from '@/components/layout/ModeToggle'
import ProfileDropdown from '@/components/shared/ProfileDropdown'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { SidebarTrigger } from '@/components/ui/sidebar'

const Header = () => {
  const pathname = usePathname()

  const segments = pathname.split('/').filter(Boolean)

  return (
    <header className='bg-card sticky top-0 z-50 border-b'>
      <div className='mx-auto flex max-w-360 items-center justify-between gap-6 px-4 py-2 sm:px-6'>
        <div className='flex items-center gap-4'>
          <SidebarTrigger className='[&_svg]:size-5!' />
          <Separator orientation='vertical' className='hidden h-4! data-vertical:self-center sm:block' />
          <Breadcrumb className='hidden sm:block'>
            <BreadcrumbList>
              {segments.map((segment, index) => {
                const isLast = index === segments.length - 1
                const label = segment.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
                const href = '/' + segments.slice(0, index + 1).join('/')

                return (
                  <Fragment key={href}>
                    <BreadcrumbItem>
                      {isLast ? <BreadcrumbPage>{label}</BreadcrumbPage> : <BreadcrumbLink>{label}</BreadcrumbLink>}
                    </BreadcrumbItem>
                    {!isLast && <BreadcrumbSeparator />}
                  </Fragment>
                )
              })}
            </BreadcrumbList>
          </Breadcrumb>
        </div>
        <div className='flex items-center gap-1.5'>
          {/* GitHub Button */}
          <div className='pt-2 max-md:hidden'>
            <a
              className='github-button'
              href='https://github.com/shadcnstudio/shadcn-nextjs-admincn-admin-template-free'
              data-icon='octicon-star'
              data-size='large'
              data-show-count='true'
              aria-label='Star shadcnstudio/shadcn-studio on GitHub'
            >
              Star
            </a>
          </div>
          <script async defer src='https://buttons.github.io/buttons.js'></script>
          <ModeToggle />
          <LanguageDropdown
            trigger={
              <Button variant='ghost' size='icon-lg'>
                <LanguagesIcon />
              </Button>
            }
          />
          <ProfileDropdown />
        </div>
      </div>
    </header>
  )
}

export default Header
