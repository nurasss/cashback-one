// One outline icon family: 24×24 grid, 2px round strokes (Lucide geometry, ISC licence).
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { theme } from '../theme';

export type IconName =
  | 'home' | 'gift' | 'bell' | 'user' | 'qr' | 'arrowLeft' | 'chevronRight' | 'crown' | 'percent' | 'scan'
  | 'card' | 'cart' | 'plus' | 'minus' | 'logout' | 'history' | 'check' | 'tag' | 'wallet' | 'x';

const paths: Record<IconName, React.ReactNode> = {
  home: <><Path d="M3 10.5 12 3l9 7.5" /><Path d="M5 9.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.5" /><Path d="M9.5 16h5" /></>,
  gift: <><Rect x="3" y="8" width="18" height="4" rx="1" /><Path d="M12 8v13" /><Path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7" /><Path d="M7.5 8a2.5 2.5 0 0 1 0-5C10 3 12 8 12 8s2-5 4.5-5a2.5 2.5 0 0 1 0 5" /></>,
  bell: <><Path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><Path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></>,
  user: <><Circle cx="12" cy="12" r="10" /><Circle cx="12" cy="10" r="3" /><Path d="M7 20.66V19a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v1.66" /></>,
  qr: <><Rect x="3" y="3" width="7" height="7" rx="1" /><Rect x="14" y="3" width="7" height="7" rx="1" /><Rect x="3" y="14" width="7" height="7" rx="1" /><Path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 20h4M20 17v3" /></>,
  arrowLeft: <><Path d="M19 12H5" /><Path d="m12 19-7-7 7-7" /></>,
  chevronRight: <Path d="m9 18 6-6-6-6" />,
  crown: <><Path d="M2 18h20" /><Path d="m3 7 4.5 4L12 4l4.5 7L21 7l-2 11H5z" /></>,
  percent: <><Path d="M19 5 5 19" /><Circle cx="6.5" cy="6.5" r="2.5" /><Circle cx="17.5" cy="17.5" r="2.5" /></>,
  scan: <><Path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" /><Path d="M8 12h8" /></>,
  card: <><Rect x="2" y="5" width="20" height="14" rx="2" /><Path d="M2 10h20M6 15h4" /></>,
  cart: <><Circle cx="8" cy="21" r="1" /><Circle cx="19" cy="21" r="1" /><Path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12" /></>,
  plus: <><Path d="M12 5v14" /><Path d="M5 12h14" /></>,
  minus: <Path d="M5 12h14" />,
  logout: <><Path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><Path d="m16 17 5-5-5-5" /><Path d="M21 12H9" /></>,
  history: <><Path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><Path d="M3 3v5h5" /><Path d="M12 7v5l4 2" /></>,
  check: <Path d="M20 6 9 17l-5-5" />,
  tag: <><Path d="M12.59 2.59A2 2 0 0 0 11.17 2H4a2 2 0 0 0-2 2v7.17a2 2 0 0 0 .59 1.42l8.7 8.7a2.43 2.43 0 0 0 3.42 0l6.58-6.58a2.43 2.43 0 0 0 0-3.42z" /><Circle cx="7.5" cy="7.5" r="1.5" /></>,
  wallet: <><Path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1" /><Path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4" /></>,
  x: <><Path d="M18 6 6 18" /><Path d="m6 6 12 12" /></>,
};

// `filled` paints the shape solid (active tab, as in the design); the inner detail of the house stays white.
export function Icon({ name, size = 24, color = theme.colors.text, strokeWidth = 2, filled = false }: { name: IconName; size?: number; color?: string; strokeWidth?: number; filled?: boolean }) {
  return <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
    {filled && name === 'home'
      ? <><Path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z" fill={color} /><Path d="M9.5 16h5" stroke="#FFFFFF" /></>
      : paths[name]}
  </Svg>;
}
