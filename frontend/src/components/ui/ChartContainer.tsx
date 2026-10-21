import styles from './ChartContainer.module.css'

interface ChartContainerProps {
  title?: string
  children: React.ReactNode
  height?: number
}

export default function ChartContainer({ title, children, height = 280 }: ChartContainerProps) {
  return (
    <figure className={styles.container} aria-label={title}>
      {title && <figcaption className={styles.title}>{title}</figcaption>}
      <div style={{ height }} className={styles.chart}>
        {children}
      </div>
    </figure>
  )
}
