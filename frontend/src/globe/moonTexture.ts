// ABOUTME: Builds the globe texture by stitching NASA Moon Trek WMTS tiles of the LRO WAC mosaic
// ABOUTME: Tiles load progressively into one equirectangular canvas; no imagery is stored in the repo

import { CanvasTexture, SRGBColorSpace } from 'three'

// LRO WAC global mosaic served by NASA Moon Trek (JPL); geographic tile grid, 2 x 1 tiles of
// 256 px at level 0, top-left corner at (lon -180, lat 90). See the layer's WMTSCapabilities.xml.
const TILE_URL =
  'https://trek.nasa.gov/tiles/Moon/EQ/LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm'
const TILE_SIZE = 256

export const MOON_TEXTURE_ATTRIBUTION = 'LRO WAC global mosaic, NASA / GSFC / ASU, via NASA Moon Trek'

/**
 * Create an equirectangular Moon texture and fill it as tiles arrive.
 *
 * @param level WMTS zoom level; the canvas is 512 * 2^level px wide (level 3 = 4096 x 2048).
 * @param onProgress Called after each tile is drawn, so the caller can re-render.
 */
export function createMoonTexture(level: number, onProgress: () => void): CanvasTexture {
  const columns = 2 ** (level + 1)
  const rows = 2 ** level
  const canvas = document.createElement('canvas')
  canvas.width = columns * TILE_SIZE
  canvas.height = rows * TILE_SIZE
  const context = canvas.getContext('2d')!
  context.fillStyle = '#3a3a3a'
  context.fillRect(0, 0, canvas.width, canvas.height)

  const texture = new CanvasTexture(canvas)
  texture.colorSpace = SRGBColorSpace
  texture.anisotropy = 8

  for (let row = 0; row < rows; row++) {
    for (let column = 0; column < columns; column++) {
      const image = new Image()
      image.crossOrigin = 'anonymous'
      image.onload = () => {
        context.drawImage(image, column * TILE_SIZE, row * TILE_SIZE)
        texture.needsUpdate = true
        onProgress()
      }
      image.src = `${TILE_URL}/${level}/${row}/${column}.jpg`
    }
  }
  return texture
}
