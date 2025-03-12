import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

data = pd.read_csv("/Rawdataplane.csv")
d = {'time / min':data["Time (s)"]/60, 'pressure / hPa':data["Pressure (hPa)"]}
df = pd.DataFrame(data=d)
sns.relplot(data=df, kind="line",x= "time / min", y="pressure / hPa"
            
            ) 
plt.axhline(y=1013, color='red') 
plt.text(60, 1000, "1013 hPa", color='red')
plt.show()