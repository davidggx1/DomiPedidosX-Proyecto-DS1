'use client'

import { useMemo, useState } from 'react'
import {
  Bell,
  ChevronDown,
  ChevronRight,
  Clock3,
  CookingPot,
  Filter,
  GripVertical,
  LayoutGrid,
  MoreHorizontal,
  RefreshCw,
  Search,
  SlidersHorizontal,
  Utensils,
  Wifi,
} from 'lucide-react'

const columns = [
  { id: 'recibido', label: 'Recibido', tone: 'amber', hint: 'Por preparar' },
  { id: 'en_preparacion', label: 'En preparación', tone: 'blue', hint: 'En cocina' },
  { id: 'listo_despacho', label: 'Listo para despacho', tone: 'green', hint: 'Esperando repartidor' },
] as const

type ColumnId = (typeof columns)[number]['id']
type Order = {
  id: number
  number: string
  state: ColumnId
  time: string
  minutes: number
  items: string[]
  note?: string
  changes?: boolean
  customer: string
  zone: string
}

const initialOrders: Order[] = [
  { id: 1, number: '#1048', state: 'recibido', time: '12:32 p. m.', minutes: 8, items: ['2x Combo Clásico', '1x Papas grandes'], note: 'Sin cebolla en una hamburguesa', changes: true, customer: 'Laura Méndez', zone: 'Norte' },
  { id: 2, number: '#1049', state: 'recibido', time: '12:35 p. m.', minutes: 5, items: ['1x Pizza mediana', '2x Coca-Cola'], customer: 'Andrés Rojas', zone: 'Centro' },
  { id: 3, number: '#1050', state: 'recibido', time: '12:38 p. m.', minutes: 2, items: ['1x Hamburguesa Domi', '1x Aros de cebolla'], customer: 'Camila Torres', zone: 'Norte' },
  { id: 4, number: '#1045', state: 'en_preparacion', time: '12:21 p. m.', minutes: 19, items: ['3x Combo Familiar', '1x Brownie'], note: 'Agregar salsas de ajo', changes: true, customer: 'Mateo Silva', zone: 'Sur' },
  { id: 5, number: '#1046', state: 'en_preparacion', time: '12:25 p. m.', minutes: 15, items: ['1x Pizza grande', '1x Limonada natural'], customer: 'Sofía Vargas', zone: 'Centro' },
  { id: 6, number: '#1047', state: 'en_preparacion', time: '12:28 p. m.', minutes: 12, items: ['2x Wrap de pollo'], note: 'Una porción sin picante', changes: true, customer: 'Nicolás Pérez', zone: 'Norte' },
  { id: 7, number: '#1041', state: 'listo_despacho', time: '12:08 p. m.', minutes: 32, items: ['1x Combo Clásico', '1x Nuggets x10'], customer: 'Valentina Díaz', zone: 'Centro' },
  { id: 8, number: '#1043', state: 'listo_despacho', time: '12:15 p. m.', minutes: 25, items: ['2x Pizza mediana'], customer: 'Juan Esteban', zone: 'Sur' },
]

const nextState: Record<ColumnId, ColumnId | undefined> = {
  recibido: 'en_preparacion',
  en_preparacion: 'listo_despacho',
  listo_despacho: undefined,
}

const nextLabel: Record<ColumnId, string> = {
  recibido: 'Comenzar preparación',
  en_preparacion: 'Marcar como listo',
  listo_despacho: '',
}

export function KanbanDashboard() {
  const [orders, setOrders] = useState(initialOrders)
  const [activeColumn, setActiveColumn] = useState<ColumnId>('recibido')
  const [location, setLocation] = useState('Todas las sedes')
  const [query, setQuery] = useState('')
  const [showFilters, setShowFilters] = useState(false)
  const [lastUpdated, setLastUpdated] = useState('hace 8 s')

  const filteredOrders = useMemo(() => orders.filter((order) => {
    const matchesLocation = location === 'Todas las sedes' || order.zone === location
    const matchesQuery = `${order.number} ${order.customer} ${order.items.join(' ')}`.toLowerCase().includes(query.toLowerCase())
    return matchesLocation && matchesQuery
  }), [orders, location, query])

  const moveOrder = (id: number, state: ColumnId) => {
    setOrders((current) => current.map((order) => order.id === id ? { ...order, state } : order))
    setLastUpdated('justo ahora')
  }

  return (
    <main className="min-h-screen bg-[#f7f8fa] text-[#14212b]">
      <header className="border-b border-[#e6e9ed] bg-white">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-5 py-4 lg:px-10">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-[#f35d36] text-white shadow-sm shadow-orange-200"><Utensils size={21} strokeWidth={2.4} /></div>
            <div><p className="text-[11px] font-bold uppercase tracking-[.2em] text-[#f35d36]">DomiPedidos</p><p className="text-sm font-semibold text-[#63707b]">Operaciones de cocina</p></div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden items-center gap-2 rounded-full bg-[#effaf3] px-3 py-2 text-xs font-semibold text-[#25844a] sm:flex"><span className="size-2 rounded-full bg-[#32ae61]" /> Tiempo real activo</div>
            <button aria-label="Notificaciones" className="relative rounded-xl p-2 text-[#63707b] transition hover:bg-[#f4f5f6]"><Bell size={19} /><span className="absolute right-1 top-1 size-2 rounded-full bg-[#f35d36] ring-2 ring-white" /></button>
            <div className="hidden h-8 w-px bg-[#e6e9ed] sm:block" />
            <div className="flex items-center gap-2"><div className="flex size-8 items-center justify-center rounded-full bg-[#183c4a] text-xs font-bold text-white">JF</div><div className="hidden text-left sm:block"><p className="text-xs font-bold">Juan Fernando</p><p className="text-[11px] text-[#7d8992]">Cocina · Norte</p></div><ChevronDown size={15} className="text-[#7d8992]" /></div>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1440px] px-5 py-8 lg:px-10">
        <div className="mb-7 flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div><div className="mb-2 flex items-center gap-2 text-xs font-semibold text-[#7d8992]"><LayoutGrid size={14} /> Tablero / Cocina</div><h1 className="text-3xl font-bold tracking-[-.04em] text-[#14212b] sm:text-4xl">Pedidos de cocina</h1><p className="mt-2 text-sm text-[#6d7a84]">Gestiona cada pedido desde que llega hasta que está listo para despacho.</p></div>
          <button onClick={() => setLastUpdated('justo ahora')} className="flex w-fit items-center gap-2 rounded-xl border border-[#dfe4e8] bg-white px-4 py-2.5 text-sm font-semibold text-[#53616c] shadow-sm transition hover:border-[#f35d36] hover:text-[#f35d36]"><RefreshCw size={16} /> Actualizar tablero</button>
        </div>

        <section className="mb-7 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Pedidos activos" value={orders.length} color="text-[#14212b]" />
          <Stat label="Por preparar" value={orders.filter(o => o.state === 'recibido').length} color="text-[#d98719]" />
          <Stat label="En cocina" value={orders.filter(o => o.state === 'en_preparacion').length} color="text-[#3276bd]" />
          <Stat label="Listos" value={orders.filter(o => o.state === 'listo_despacho').length} color="text-[#25844a]" />
        </section>

        <div className="mb-5 flex flex-col gap-3 rounded-2xl border border-[#e6e9ed] bg-white p-3 shadow-[0_2px_8px_rgba(20,33,43,.03)] sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-1 overflow-x-auto"><Filter size={16} className="mx-2 shrink-0 text-[#87929a]" />{columns.map(column => <button key={column.id} onClick={() => setActiveColumn(column.id)} className={`whitespace-nowrap rounded-lg px-3 py-2 text-sm font-semibold transition ${activeColumn === column.id ? 'bg-[#183c4a] text-white' : 'text-[#75818a] hover:bg-[#f3f5f6]'}`}>{column.label}<span className={`ml-2 rounded-full px-1.5 py-0.5 text-[11px] ${activeColumn === column.id ? 'bg-white/15 text-white' : 'bg-[#f0f2f3] text-[#7d8992]'}`}>{orders.filter(o => o.state === column.id).length}</span></button>)}</div>
          <div className="flex items-center gap-2"><div className="relative min-w-0 flex-1 sm:w-52"><Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#9aa4ab]" /><input aria-label="Buscar pedidos" value={query} onChange={e => setQuery(e.target.value)} placeholder="Buscar pedido..." className="w-full rounded-lg border-0 bg-[#f6f7f8] py-2 pl-9 pr-3 text-sm outline-none ring-[#f35d36] placeholder:text-[#a0a9b0] focus:ring-2" /></div><button onClick={() => setShowFilters(!showFilters)} aria-expanded={showFilters} className={`rounded-lg p-2.5 ${showFilters ? 'bg-[#fff0eb] text-[#f35d36]' : 'bg-[#f6f7f8] text-[#697680]'}`}><SlidersHorizontal size={16} /></button></div>
        </div>
        {showFilters && <div className="mb-5 flex items-center gap-3 rounded-xl border border-[#f1dfd8] bg-[#fffaf8] p-3 text-sm"><span className="font-semibold text-[#53616c]">Sede:</span><select value={location} onChange={e => setLocation(e.target.value)} className="rounded-lg border border-[#e6d5ce] bg-white px-3 py-2 text-sm outline-none"><option>Todas las sedes</option><option>Norte</option><option>Centro</option><option>Sur</option></select><span className="text-xs text-[#8c989f]">Los cambios se aplican en tiempo real</span></div>}

        <div className="mb-4 flex items-center justify-between text-xs text-[#8c989f]"><div className="flex items-center gap-2"><span className="flex items-center gap-1.5 font-semibold text-[#25844a]"><Wifi size={13} /> Conectado por WebSocket</span><span>·</span><span>Última actualización: {lastUpdated}</span></div><span className="hidden sm:block">Arrastra una tarjeta o usa los botones para cambiar su estado</span></div>

        <div className="grid gap-5 lg:grid-cols-3">
          {columns.map(column => <KanbanColumn key={column.id} column={column} orders={filteredOrders.filter(order => order.state === column.id)} onMove={moveOrder} />)}
        </div>
      </div>
    </main>
  )
}

function Stat({ label, value, color }: { label: string, value: number, color: string }) { return <div className="rounded-2xl border border-[#e6e9ed] bg-white p-4 shadow-[0_2px_8px_rgba(20,33,43,.03)]"><p className="text-xs font-semibold text-[#87929a]">{label}</p><p className={`mt-1 text-2xl font-bold tracking-[-.04em] ${color}`}>{value}</p></div> }

function KanbanColumn({ column, orders, onMove }: { column: typeof columns[number], orders: Order[], onMove: (id: number, state: ColumnId) => void }) {
  const tone = { amber: { bar: 'bg-[#f0b34b]', count: 'bg-[#fff4dd] text-[#b57410]', dot: 'bg-[#f0b34b]' }, blue: { bar: 'bg-[#4b92cf]', count: 'bg-[#e8f2fb] text-[#3276bd]', dot: 'bg-[#4b92cf]' }, green: { bar: 'bg-[#4cae70]', count: 'bg-[#e8f7ed] text-[#25844a]', dot: 'bg-[#4cae70]' } }[column.tone]
  return <section className="min-w-0 rounded-2xl border border-[#e1e6e9] bg-[#f0f2f3] p-3.5"><div className="mb-4 flex items-center justify-between px-1"><div className="flex items-center gap-2"><span className={`size-2.5 rounded-full ${tone.dot}`} /><div><h2 className="text-sm font-bold text-[#273640]">{column.label}</h2><p className="mt-0.5 text-[11px] text-[#8a969e]">{column.hint}</p></div></div><span className={`rounded-full px-2.5 py-1 text-xs font-bold ${tone.count}`}>{orders.length}</span></div><div className="space-y-3">{orders.map(order => <OrderCard key={order.id} order={order} accent={tone.bar} onMove={onMove} />)}{orders.length === 0 && <div className="rounded-xl border border-dashed border-[#cbd3d8] py-12 text-center text-sm text-[#9aa4ab]">No hay pedidos aquí</div>}</div></section>
}

function OrderCard({ order, accent, onMove }: { order: Order, accent: string, onMove: (id: number, state: ColumnId) => void }) {
  const next = nextState[order.state]
  return <article className="group overflow-hidden rounded-xl border border-[#e3e7ea] bg-white shadow-[0_3px_10px_rgba(20,33,43,.045)] transition hover:-translate-y-0.5 hover:shadow-[0_8px_20px_rgba(20,33,43,.08)]"><div className={`h-1 ${accent}`} /><div className="p-4"><div className="mb-3 flex items-start justify-between"><div><div className="flex items-center gap-2"><h3 className="text-base font-bold text-[#182832]">{order.number}</h3>{order.changes && <span className="rounded bg-[#fff0eb] px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-[#db6849]">Cambios</span>}</div><p className="mt-1 text-[11px] text-[#849099]">{order.customer} · {order.zone}</p></div><button aria-label={`Más opciones para ${order.number}`} className="text-[#a3adb3] opacity-0 transition group-hover:opacity-100"><MoreHorizontal size={18} /></button></div><div className="space-y-1.5 border-y border-[#eef0f1] py-3">{order.items.map(item => <p key={item} className="text-xs font-medium text-[#52616a]">{item}</p>)}{order.note && <p className="mt-2 flex items-start gap-1.5 text-[11px] font-semibold text-[#d66b4b]"><span className="mt-0.5 size-1.5 shrink-0 rounded-full bg-[#f28a65]" />{order.note}</p>}</div><div className="mt-3 flex items-center justify-between"><span className="flex items-center gap-1.5 text-[11px] text-[#89949b]"><Clock3 size={13} /> {order.time} <span className="text-[#c1c7cb]">·</span> {order.minutes} min</span><GripVertical size={16} className="text-[#c2c9ce]" /></div>{next && <button onClick={() => onMove(order.id, next)} className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg bg-[#f7f8f8] py-2 text-xs font-bold text-[#4d606a] transition hover:bg-[#183c4a] hover:text-white">{nextLabel[order.state]} <ChevronRight size={14} /></button>}</div></article>
}
