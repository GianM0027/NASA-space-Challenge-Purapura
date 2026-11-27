// ABOUTME: 3D Moon globe (spec UI-1): NASA texture, sunlight at the selected time, Earth, sites
// ABOUTME: Owner: Gian. Plain three.js inside one React component; props in, picks out through callbacks

import { useEffect, useRef, useState } from 'react'
import {
  AmbientLight,
  BufferGeometry,
  Color,
  DirectionalLight,
  ConeGeometry,
  CylinderGeometry,
  DoubleSide,
  Group,
  Line,
  LineBasicMaterial,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  RingGeometry,
  Raycaster,
  Scene,
  SphereGeometry,
  Vector2,
  Vector3,
  WebGLRenderer,
} from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { GeoPoint, Site, SkyState } from '../api/contracts'
import { latLonToVector, vectorToLatLon } from './geo'
import { createMoonTexture } from './moonTexture'

export type GlobeFocus = { lat_deg: number; lon_deg: number; nonce: number }

type Props = {
  sites: Site[]
  /** Currently evaluated point (catalog site or custom), shown with a highlighted marker. */
  selected: GeoPoint | null
  /** Sun and Earth sub-points; null until the backend answers. */
  sky: SkyState | null
  /** When true the whole surface is evenly lit, to pick sites that are in the dark. */
  uniformLight: boolean
  /** Change to move the camera above a point; `nonce` makes repeated requests distinct. */
  focus: GlobeFocus | null
  onPickSite: (siteId: string) => void
  onPickLocation: (point: GeoPoint) => void
}

const STATUS_COLORS: Record<Site['status'], string> = {
  landed: '#ffd166',
  planned: '#4cc9f0',
  candidate: '#b388ff',
  custom: '#ff7ab6',
}
const MARKER_RADIUS = 0.012
const HIT_RADIUS = 0.03 // invisible, larger pick target around each marker
const EARTH_DISTANCE = 1.9 // globe radii; a direction indicator, not to scale
const EARTH_MARKER_RADIUS = 0.022 // globe radii; was 0.06, which covered the legend near the camera
const CLICK_TOLERANCE_PX = 4

type Engine = {
  scene: Scene
  camera: PerspectiveCamera
  controls: OrbitControls
  moon: Mesh
  sun: DirectionalLight
  ambient: AmbientLight
  earth: Group
  markers: Group
  selection: Group
}

const vector = (lat: number, lon: number, radius = 1) =>
  new Vector3(...latLonToVector(lat, lon, radius))

/**
 * Marker of the selected point, in globe units: a thin ring lying on the ground around the point
 * and an arrow standing above it, its tip pointing at the ring's center. Built along +Z (the local
 * surface normal) and turned onto the surface where it is placed.
 */
function selectionMarker(): Group {
  const material = new MeshBasicMaterial({ color: '#ffffff', side: DoubleSide })
  const marker = new Group()
  // Ring about the size of a site marker, so the point it surrounds stays visible.
  const ring = new Mesh(new RingGeometry(MARKER_RADIUS * 0.9, MARKER_RADIUS * 1.15, 32), material)
  ring.position.z = 0.002
  marker.add(ring)
  // Cones and cylinders are built along +Y: rotating by -90 degrees about X points them at -Z.
  const head = new Mesh(new ConeGeometry(MARKER_RADIUS * 0.45, MARKER_RADIUS * 1.2, 16), material)
  head.rotation.x = -Math.PI / 2
  head.position.z = MARKER_RADIUS * 1.6
  marker.add(head)
  const shaft = new Mesh(
    new CylinderGeometry(MARKER_RADIUS * 0.12, MARKER_RADIUS * 0.12, MARKER_RADIUS * 2, 8),
    material,
  )
  shaft.rotation.x = -Math.PI / 2
  shaft.position.z = MARKER_RADIUS * 3.2
  marker.add(shaft)
  return marker
}

/** Interactive Moon globe; fills its parent element. */
export function MoonGlobe(props: Props) {
  const { sites, selected, sky, uniformLight, focus, onPickSite, onPickLocation } = props
  const hostRef = useRef<HTMLDivElement>(null)
  const engineRef = useRef<Engine | null>(null)
  const callbacks = useRef({ onPickSite, onPickLocation })
  const [hover, setHover] = useState<{ name: string; x: number; y: number } | null>(null)

  useEffect(() => {
    callbacks.current = { onPickSite, onPickLocation }
  }, [onPickSite, onPickLocation])

  // Scene setup, once.
  useEffect(() => {
    const host = hostRef.current!
    const renderer = new WebGLRenderer({ antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    host.appendChild(renderer.domElement)

    const scene = new Scene()
    scene.background = new Color('#05070c')
    const camera = new PerspectiveCamera(40, 1, 0.01, 100)
    camera.position.copy(vector(10, 0, 3.2))

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enablePan = false
    controls.enableDamping = true
    controls.minDistance = 1.12
    controls.maxDistance = 6
    // Slower rotation when close to the surface, so fine positioning stays possible.
    const tuneSpeed = () => {
      controls.rotateSpeed = Math.min(1, (camera.position.length() - 1) / 2)
    }
    controls.addEventListener('change', tuneSpeed)
    tuneSpeed()

    const texture = createMoonTexture(3, () => undefined)
    const moon = new Mesh(
      new SphereGeometry(1, 128, 64),
      new MeshStandardMaterial({ map: texture, roughness: 1, metalness: 0 }),
    )
    scene.add(moon)

    const sun = new DirectionalLight('#ffffff', 3)
    const ambient = new AmbientLight('#ffffff', 0.12)
    scene.add(sun, ambient)

    const earth = new Group()
    earth.add(
      // Small: it sits between the camera and the Moon and must not cover the globe or the legend.
      new Mesh(new SphereGeometry(EARTH_MARKER_RADIUS, 24, 16), new MeshBasicMaterial({ color: '#4f8fff' })),
      new Line(
        new BufferGeometry().setFromPoints([new Vector3(0, 0, 0), new Vector3(0, 0, 0)]),
        new LineBasicMaterial({ color: '#4f8fff', transparent: true, opacity: 0.6 }),
      ),
    )
    earth.visible = false
    scene.add(earth)

    const markers = new Group()
    scene.add(markers)
    const selection = selectionMarker()
    selection.visible = false
    scene.add(selection)

    engineRef.current = { scene, camera, controls, moon, sun, ambient, earth, markers, selection }

    const resize = () => {
      const { clientWidth, clientHeight } = host
      renderer.setSize(clientWidth, clientHeight)
      camera.aspect = clientWidth / Math.max(clientHeight, 1)
      camera.updateProjectionMatrix()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(host)
    resize()

    const raycaster = new Raycaster()
    const pointer = new Vector2()
    const cast = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect()
      pointer.set(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1,
      )
      raycaster.setFromCamera(pointer, camera)
      const moonHit = raycaster.intersectObject(moon)[0]
      const markerHit = raycaster.intersectObjects(markers.children)[0]
      // A marker behind the limb must not be pickable through the Moon.
      const site =
        markerHit && (!moonHit || markerHit.distance < moonHit.distance + HIT_RADIUS)
          ? (markerHit.object.userData as { id: string; name: string })
          : null
      return { site, moonHit, rect }
    }

    let down: { x: number; y: number } | null = null
    const onDown = (event: PointerEvent) => {
      down = { x: event.clientX, y: event.clientY }
    }
    const onUp = (event: PointerEvent) => {
      const start = down
      down = null
      if (!start) return
      if (Math.hypot(event.clientX - start.x, event.clientY - start.y) > CLICK_TOLERANCE_PX) return
      const { site, moonHit } = cast(event)
      if (site) callbacks.current.onPickSite(site.id)
      else if (moonHit) {
        const { x, y, z } = moonHit.point
        callbacks.current.onPickLocation(vectorToLatLon(x, y, z))
      }
    }
    const onMove = (event: PointerEvent) => {
      if (down) return
      const { site, rect } = cast(event)
      renderer.domElement.style.cursor = site ? 'pointer' : 'grab'
      setHover((previous) => {
        if (!site) return previous ? null : previous
        return { name: site.name, x: event.clientX - rect.left, y: event.clientY - rect.top }
      })
    }
    const canvas = renderer.domElement
    canvas.addEventListener('pointerdown', onDown)
    canvas.addEventListener('pointerup', onUp)
    canvas.addEventListener('pointermove', onMove)
    canvas.addEventListener('pointerleave', () => setHover(null))

    let frame = 0
    const loop = () => {
      controls.update()
      renderer.render(scene, camera)
      frame = requestAnimationFrame(loop)
    }
    loop()

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      controls.dispose()
      texture.dispose()
      renderer.dispose()
      host.removeChild(canvas)
      engineRef.current = null
    }
  }, [])

  // Site markers.
  useEffect(() => {
    const engine = engineRef.current
    if (!engine) return
    engine.markers.clear()
    for (const site of sites) {
      // The raycast target is an invisible sphere larger than the visible dot it carries.
      const hit = new Mesh(
        new SphereGeometry(HIT_RADIUS, 8, 6),
        new MeshBasicMaterial({ visible: false }),
      )
      hit.userData = { id: site.id, name: site.name }
      hit.position.copy(vector(site.location.lat_deg, site.location.lon_deg, 1.004))
      hit.add(
        new Mesh(
          new SphereGeometry(MARKER_RADIUS, 12, 8),
          new MeshBasicMaterial({ color: STATUS_COLORS[site.status] }),
        ),
      )
      engine.markers.add(hit)
    }
  }, [sites])

  // Selected point.
  useEffect(() => {
    const engine = engineRef.current
    if (!engine) return
    engine.selection.visible = selected !== null
    if (selected) {
      const normal = vector(selected.lat_deg, selected.lon_deg).normalize()
      engine.selection.position.copy(normal)
      engine.selection.quaternion.setFromUnitVectors(new Vector3(0, 0, 1), normal)
    }
  }, [selected])

  // Sunlight and Earth direction.
  useEffect(() => {
    const engine = engineRef.current
    if (!engine) return
    engine.sun.visible = !uniformLight && sky !== null
    engine.ambient.intensity = uniformLight || sky === null ? 2.2 : 0.12
    engine.earth.visible = sky !== null
    if (!sky) return
    engine.sun.position.copy(vector(sky.subsolar.lat_deg, sky.subsolar.lon_deg, 10))
    const direction = vector(sky.sub_earth.lat_deg, sky.sub_earth.lon_deg)
    const [ball, line] = engine.earth.children as [Mesh, Line]
    ball.position.copy(direction.clone().multiplyScalar(EARTH_DISTANCE))
    line.geometry.setFromPoints([direction.clone(), ball.position.clone()])
  }, [sky, uniformLight])

  // Camera moves.
  useEffect(() => {
    const engine = engineRef.current
    if (!engine || !focus) return
    const distance = engine.camera.position.length()
    // Exactly over a pole the orbit controls are degenerate (camera up = view axis).
    const lat = Math.max(-89, Math.min(89, focus.lat_deg))
    engine.camera.position.copy(vector(lat, focus.lon_deg, distance))
    engine.controls.update()
  }, [focus])

  return (
    <div className="globe" ref={hostRef}>
      {hover && (
        <div className="globe-tooltip" style={{ left: hover.x + 12, top: hover.y + 12 }}>
          {hover.name}
        </div>
      )}
    </div>
  )
}
