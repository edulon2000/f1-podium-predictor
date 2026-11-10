import fs from 'node:fs'
import path from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The site is static: the JSON exported by `f1pred-export` (../site_data) is served under /data.
// Dev: a middleware serves it straight from site_data. Build: it is copied into dist/data.
const SITE_DATA = path.resolve(__dirname, '../site_data')

function siteData(): Plugin {
  return {
    name: 'site-data',
    configureServer(server) {
      server.middlewares.use('/data', (req, res) => {
        const file = path.join(SITE_DATA, decodeURIComponent((req.url ?? '/').split('?')[0]))
        if (!file.startsWith(SITE_DATA) || !file.endsWith('.json') || !fs.existsSync(file)) {
          res.statusCode = 404
          return res.end()
        }
        res.setHeader('Content-Type', 'application/json')
        fs.createReadStream(file).pipe(res)
      })
    },
    closeBundle() {
      if (!fs.existsSync(SITE_DATA)) throw new Error(`site_data not found at ${SITE_DATA}`)
      fs.cpSync(SITE_DATA, path.resolve(__dirname, 'dist/data'), { recursive: true })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), siteData()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
})
