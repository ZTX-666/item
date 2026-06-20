import { Routes, Route } from 'react-router-dom';
import { Dashboard } from './pages/Dashboard';
import NewDiary from './NewDiary';

function App() {
  return (
    <Routes>
      <Route path="/" element={<NewDiary />} />
      <Route path="/dashboard" element={<Dashboard />} />
    </Routes>
  );
}

export default App;
