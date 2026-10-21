import { Outlet } from 'react-router-dom'
import AppNavBar from './AppNavBar'
import styles from './AppShell.module.css'

export default function AppShell() {
  return (
    <div className={styles.shell} data-theme="workspace">
      <AppNavBar />
      <main className={styles.main} id="main-content">
        <Outlet />
      </main>
    </div>
  )
}
