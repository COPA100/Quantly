import { createBrowserRouter } from 'react-router-dom'
import RootLayout from './components/RootLayout'
import HomePage from './pages/HomePage'
import NotFoundPage from './pages/NotFoundPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <RootLayout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
