import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppRouter } from './layout/AppRouter';
import '@fontsource/roboto/cyrillic-ext-400.css';
import '@fontsource/roboto/cyrillic-400.css';
import '@fontsource/roboto/latin-400.css';
import '@fontsource/roboto/cyrillic-ext-500.css';
import '@fontsource/roboto/cyrillic-500.css';
import '@fontsource/roboto/latin-500.css';
import '@fontsource/roboto/cyrillic-ext-600.css';
import '@fontsource/roboto/cyrillic-600.css';
import '@fontsource/roboto/latin-600.css';
import '@fontsource/roboto/cyrillic-ext-700.css';
import '@fontsource/roboto/cyrillic-700.css';
import '@fontsource/roboto/latin-700.css';
import './styles/landing.css';
import './styles/admin.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppRouter />
  </React.StrictMode>,
);
