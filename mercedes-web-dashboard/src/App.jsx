import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/button.jsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.jsx'
import { Badge } from '@/components/ui/badge.jsx'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs.jsx'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select.jsx'
import { Input } from '@/components/ui/input.jsx'
import { Label } from '@/components/ui/label.jsx'
import { Progress } from '@/components/ui/progress.jsx'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert.jsx'
import { 
  Car, 
  Gauge, 
  Thermometer, 
  Zap, 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Activity,
  Brain,
  History,
  Settings,
  Wifi,
  WifiOff,
  TrendingUp,
  TrendingDown,
  Minus
} from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts'
import './App.css'

function App() {
  // Connection state
  const [connectionStatus, setConnectionStatus] = useState('disconnected')
  const [selectedProtocol, setSelectedProtocol] = useState('DEMO')
  const [selectedPort, setSelectedPort] = useState('DEMO')
  const [vehicleId, setVehicleId] = useState('')
  const [availablePorts, setAvailablePorts] = useState(['DEMO'])

  // Real-time data
  const [obdData, setObdData] = useState({
    ENGINE_RPM: { value: 0, unit: 'rpm', status: 'ok' },
    COOLANT_TEMP: { value: 0, unit: '°C', status: 'ok' },
    ENGINE_LOAD: { value: 0, unit: '%', status: 'ok' },
    SPEED: { value: 0, unit: 'km/h', status: 'ok' },
    FUEL_LEVEL: { value: 0, unit: '%', status: 'ok' },
    OIL_PRESSURE: { value: 0, unit: 'bar', status: 'ok' },
    TRANS_TEMP: { value: 0, unit: '°C', status: 'ok' },
    AIR_PRESSURE_FL: { value: 0, unit: 'bar', status: 'ok' },
    AIR_PRESSURE_FR: { value: 0, unit: 'bar', status: 'ok' }
  })

  // Chart data
  const [chartData, setChartData] = useState([])
  const [anomalies, setAnomalies] = useState([])
  const [predictions, setPredictions] = useState([])
  const [tripHistory, setTripHistory] = useState([])
  const [aiAnalysis, setAiAnalysis] = useState(null)

  // WebSocket connection
  const ws = useRef(null)

  // Initialize WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws`
      
      ws.current = new WebSocket(wsUrl)
      
      ws.current.onopen = () => {
        console.log('WebSocket connected')
      }
      
      ws.current.onmessage = (event) => {
        const data = JSON.parse(event.data)
        handleWebSocketMessage(data)
      }
      
      ws.current.onclose = () => {
        console.log('WebSocket disconnected')
        // Attempt to reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000)
      }
      
      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
    }

    connectWebSocket()

    return () => {
      if (ws.current) {
        ws.current.close()
      }
    }
  }, [])

  // Handle WebSocket messages
  const handleWebSocketMessage = (data) => {
    switch (data.type) {
      case 'data_update':
        setObdData(prev => ({
          ...prev,
          [data.name]: {
            value: data.value,
            unit: data.unit,
            status: 'ok',
            timestamp: data.timestamp
          }
        }))
        
        // Update chart data
        setChartData(prev => {
          const newData = [...prev, {
            time: new Date(data.timestamp).toLocaleTimeString(),
            [data.name]: data.value
          }]
          return newData.slice(-50) // Keep last 50 points
        })
        break
        
      case 'status_update':
        setConnectionStatus(data.status)
        break
        
      case 'prediction_update':
        setPredictions(data.predictions)
        break
        
      case 'anomaly_detected':
        setAnomalies(prev => [{
          id: Date.now(),
          score: data.score,
          data: data.data,
          timestamp: new Date().toLocaleString(),
          severity: data.score > 0.8 ? 'high' : data.score > 0.5 ? 'medium' : 'low'
        }, ...prev.slice(0, 9)]) // Keep last 10 anomalies
        break
    }
  }

  // API calls
  const fetchAvailablePorts = async () => {
    try {
      const response = await fetch('/api/ports')
      const data = await response.json()
      setAvailablePorts(data.ports)
    } catch (error) {
      console.error('Failed to fetch ports:', error)
    }
  }

  const connectOBD = async () => {
    try {
      const response = await fetch('/api/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          protocol: selectedProtocol,
          port: selectedPort,
          vehicle_id: vehicleId
        })
      })
      
      if (response.ok) {
        setConnectionStatus('connecting')
      }
    } catch (error) {
      console.error('Failed to connect:', error)
    }
  }

  const disconnectOBD = async () => {
    try {
      const response = await fetch('/api/disconnect', { method: 'POST' })
      if (response.ok) {
        setConnectionStatus('disconnecting')
      }
    } catch (error) {
      console.error('Failed to disconnect:', error)
    }
  }

  const fetchTripHistory = async () => {
    try {
      const response = await fetch('/api/trip-history')
      const data = await response.json()
      setTripHistory(data.trips)
    } catch (error) {
      console.error('Failed to fetch trip history:', error)
    }
  }

  // Load trip history on component mount
  useEffect(() => {
    fetchTripHistory()
    fetchAvailablePorts()
  }, [])

  // Status indicator component
  const StatusIndicator = ({ status }) => {
    const statusConfig = {
      connected: { icon: Wifi, color: 'text-green-500', bg: 'bg-green-100', text: 'Connected' },
      connecting: { icon: Activity, color: 'text-yellow-500', bg: 'bg-yellow-100', text: 'Connecting...' },
      disconnected: { icon: WifiOff, color: 'text-red-500', bg: 'bg-red-100', text: 'Disconnected' },
      disconnecting: { icon: Activity, color: 'text-orange-500', bg: 'bg-orange-100', text: 'Disconnecting...' }
    }

    const config = statusConfig[status] || statusConfig.disconnected
    const Icon = config.icon

    return (
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${config.bg}`}>
        <Icon className={`w-4 h-4 ${config.color}`} />
        <span className={`text-sm font-medium ${config.color}`}>{config.text}</span>
      </div>
    )
  }

  // Parameter card component
  const ParameterCard = ({ title, icon: Icon, parameters }) => (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-lg">
          <Icon className="w-5 h-5" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {parameters.map(({ key, label, format = (v) => v }) => (
          <div key={key} className="flex justify-between items-center">
            <span className="text-sm text-muted-foreground">{label}:</span>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm">
                {obdData[key] ? format(obdData[key].value) : '--'}
                {obdData[key]?.unit && ` ${obdData[key].unit}`}
              </span>
              {obdData[key]?.status === 'ok' ? (
                <CheckCircle className="w-4 h-4 text-green-500" />
              ) : (
                <XCircle className="w-4 h-4 text-red-500" />
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Car className="w-8 h-8 text-primary" />
              <div>
                <h1 className="text-2xl font-bold">Mercedes W222 OBD Scanner</h1>
                <p className="text-sm text-muted-foreground">Professional Diagnostics & AI Analysis</p>
              </div>
            </div>
            <StatusIndicator status={connectionStatus} />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        <Tabs defaultValue="connection" className="space-y-6">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="connection">Connection</TabsTrigger>
            <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
            <TabsTrigger value="diagnostics">Diagnostics</TabsTrigger>
            <TabsTrigger value="trips">Trip History</TabsTrigger>
            <TabsTrigger value="ai-analysis">AI Analysis</TabsTrigger>
          </TabsList>

          {/* Connection Tab */}
          <TabsContent value="connection" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>OBD Scanner Connection</CardTitle>
                <CardDescription>
                  Connect to your Mercedes W222 via OBD-II or UDS protocol
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="protocol">Protocol</Label>
                    <Select value={selectedProtocol} onValueChange={setSelectedProtocol}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="DEMO">DEMO (Demonstration)</SelectItem>
                        <SelectItem value="OBD">OBD-II</SelectItem>
                        <SelectItem value="UDS">UDS (Mercedes)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="port">Port</Label>
                    <div className="flex gap-2">
                      <Select value={selectedPort} onValueChange={setSelectedPort}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {availablePorts.map(port => (
                            <SelectItem key={port} value={port}>{port}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <Button variant="outline" size="sm" onClick={fetchAvailablePorts}>
                        Refresh
                      </Button>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="vehicle-id">Vehicle VIN (Optional)</Label>
                    <Input
                      id="vehicle-id"
                      placeholder="WDD2220391A123456"
                      value={vehicleId}
                      onChange={(e) => setVehicleId(e.target.value)}
                    />
                  </div>
                </div>
                
                <div className="flex gap-2">
                  <Button 
                    onClick={connectOBD} 
                    disabled={connectionStatus === 'connected' || connectionStatus === 'connecting'}
                    className="flex-1"
                  >
                    {connectionStatus === 'connecting' ? 'Connecting...' : 'Connect'}
                  </Button>
                  <Button 
                    variant="outline" 
                    onClick={disconnectOBD}
                    disabled={connectionStatus === 'disconnected' || connectionStatus === 'disconnecting'}
                    className="flex-1"
                  >
                    {connectionStatus === 'disconnecting' ? 'Disconnecting...' : 'Disconnect'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Monitoring Tab */}
          <TabsContent value="monitoring" className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <ParameterCard
                title="Engine"
                icon={Zap}
                parameters={[
                  { key: 'ENGINE_RPM', label: 'RPM', format: (v) => Math.round(v) },
                  { key: 'COOLANT_TEMP', label: 'Coolant Temp', format: (v) => Math.round(v) },
                  { key: 'ENGINE_LOAD', label: 'Load', format: (v) => Math.round(v) },
                  { key: 'OIL_PRESSURE', label: 'Oil Pressure', format: (v) => v.toFixed(1) }
                ]}
              />
              
              <ParameterCard
                title="Transmission"
                icon={Settings}
                parameters={[
                  { key: 'TRANS_TEMP', label: 'ATF Temp', format: (v) => Math.round(v) },
                  { key: 'SPEED', label: 'Speed', format: (v) => Math.round(v) }
                ]}
              />
              
              <ParameterCard
                title="Air Suspension"
                icon={Gauge}
                parameters={[
                  { key: 'AIR_PRESSURE_FL', label: 'Front Left', format: (v) => v.toFixed(1) },
                  { key: 'AIR_PRESSURE_FR', label: 'Front Right', format: (v) => v.toFixed(1) }
                ]}
              />
            </div>

            {/* Real-time Chart */}
            <Card>
              <CardHeader>
                <CardTitle>Real-time Parameters</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <Tooltip />
                      <Line type="monotone" dataKey="ENGINE_RPM" stroke="#8884d8" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="COOLANT_TEMP" stroke="#82ca9d" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="SPEED" stroke="#ffc658" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Diagnostics Tab */}
          <TabsContent value="diagnostics" className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Predictive Diagnostics */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="w-5 h-5" />
                    Predictive Diagnostics
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {predictions.length > 0 ? (
                    predictions.map((prediction, index) => (
                      <Alert key={index}>
                        <AlertTriangle className="h-4 w-4" />
                        <AlertTitle>{prediction.component}</AlertTitle>
                        <AlertDescription>
                          {prediction.issue} - {prediction.timeframe}
                          <div className="mt-2">
                            <Progress value={prediction.confidence * 100} className="w-full" />
                            <span className="text-xs text-muted-foreground">
                              Confidence: {Math.round(prediction.confidence * 100)}%
                            </span>
                          </div>
                        </AlertDescription>
                      </Alert>
                    ))
                  ) : (
                    <p className="text-muted-foreground">
                      {connectionStatus === 'connected' 
                        ? 'Analyzing vehicle data for predictive insights...' 
                        : 'Connect to vehicle to start predictive analysis'
                      }
                    </p>
                  )}
                </CardContent>
              </Card>

              {/* Anomaly Detection */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5" />
                    Anomaly Detection
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {anomalies.length > 0 ? (
                    anomalies.map((anomaly) => (
                      <div key={anomaly.id} className="flex items-center justify-between p-3 border rounded-lg">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <Badge variant={
                              anomaly.severity === 'high' ? 'destructive' : 
                              anomaly.severity === 'medium' ? 'default' : 'secondary'
                            }>
                              {anomaly.severity}
                            </Badge>
                            <span className="text-sm text-muted-foreground">{anomaly.timestamp}</span>
                          </div>
                          <p className="text-sm mt-1">Score: {anomaly.score.toFixed(3)}</p>
                        </div>
                        {anomaly.severity === 'high' ? (
                          <TrendingUp className="w-4 h-4 text-red-500" />
                        ) : anomaly.severity === 'medium' ? (
                          <TrendingDown className="w-4 h-4 text-yellow-500" />
                        ) : (
                          <Minus className="w-4 h-4 text-green-500" />
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-muted-foreground">
                      {connectionStatus === 'connected' 
                        ? 'No anomalies detected' 
                        : 'Connect to vehicle to start anomaly detection'
                      }
                    </p>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Trip History Tab */}
          <TabsContent value="trips" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <History className="w-5 h-5" />
                  Trip History
                </CardTitle>
              </CardHeader>
              <CardContent>
                {tripHistory.length > 0 ? (
                  <div className="space-y-3">
                    {tripHistory.map((trip, index) => (
                      <div key={index} className="flex items-center justify-between p-4 border rounded-lg">
                        <div>
                          <p className="font-medium">{trip.start_time}</p>
                          <p className="text-sm text-muted-foreground">
                            Duration: {trip.duration || 'N/A'} | Distance: {trip.distance || 'N/A'} km
                          </p>
                        </div>
                        <Button variant="outline" size="sm">
                          View Details
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-muted-foreground">No trip history available</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* AI Analysis Tab */}
          <TabsContent value="ai-analysis" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Brain className="w-5 h-5" />
                  AI-Powered Trip Analysis
                </CardTitle>
                <CardDescription>
                  Advanced analysis using Claude AI for comprehensive insights
                </CardDescription>
              </CardHeader>
              <CardContent>
                {aiAnalysis ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="text-center">
                        <div className="text-2xl font-bold text-green-600">{aiAnalysis.driving_score}</div>
                        <div className="text-sm text-muted-foreground">Driving Score</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-blue-600">{aiAnalysis.efficiency_score}</div>
                        <div className="text-sm text-muted-foreground">Efficiency Score</div>
                      </div>
                      <div className="text-center">
                        <div className="text-2xl font-bold text-purple-600">{aiAnalysis.safety_score}</div>
                        <div className="text-sm text-muted-foreground">Safety Score</div>
                      </div>
                    </div>
                    <div className="prose max-w-none">
                      <p>{aiAnalysis.analysis}</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-muted-foreground">
                    Complete a trip to receive AI-powered analysis and insights
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

export default App
