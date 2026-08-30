import { PageHeader } from '../components/PageState'

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div>
      <PageHeader title={title} subtitle="Coming shortly — under construction in this phase." />
    </div>
  )
}
