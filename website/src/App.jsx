import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import Home from './pages/Home';
import Changelog from './pages/Changelog';
import './index.css';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/changelog" element={<Changelog />} />
      </Routes>
    </Router>
  );
}

export default App;
