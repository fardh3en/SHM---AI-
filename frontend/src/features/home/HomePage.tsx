import HomeNav from './HomeNav'
import HeroSection from './HeroSection'
import WorkflowSection from './WorkflowSection'
import CapabilitiesSection from './CapabilitiesSection'
import ProductPreview from './ProductPreview'
import HomeFooter from './HomeFooter'
import styles from './HomePage.module.css'

export default function HomePage() {
  return (
    <div className={styles.page}>
      {/* Skip to main content for keyboard users */}
      <a href="#main" className={styles.skipLink}>Skip to main content</a>

      <HomeNav />

      <main id="main">
        {/* Hero */}
        <HeroSection />

        {/* Workflow — how SHM-AI pipeline works */}
        <section id="workflow">
          <WorkflowSection />
        </section>

        {/* Product preview — dashboard schematic */}
        <section id="preview">
          <ProductPreview />
        </section>

        {/* Capabilities — grounded in actual backend */}
        <section id="capabilities">
          <CapabilitiesSection />
        </section>
      </main>

      <HomeFooter />
    </div>
  )
}
