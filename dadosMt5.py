import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
from blackScholes.bs import *
import pytz


class dadosMt5:
    def __init__(self, ativo, numDiasVol):

        # pd.set_option('display.max_columns', 500)
        # pd.set_option('display.max_row', 200)
        # pd.set_option('display.width', 3000)

        self.timezone = pytz.timezone("ETC/UTC")
        self.hoje = datetime.today()

        self.ativo = ativo
        self.valorAtivoBase = 0

        self.vencimentos = pd.DataFrame(columns=['Vencimento', 'Quantidade', 'Vencimeto_raw'])
        self.opcoes = pd.DataFrame(columns=['Codigo', 'Strike', 'Ultimo', 'Tipo', 'Estilo'])

        self.put = pd.DataFrame(columns=['Strike', 'Valor Op'])  # lista com todas PUT
        self.call = pd.DataFrame(columns=['Strike', 'Valor Op'])  # lista com todas CALL

        self.putITM = pd.DataFrame(columns=['Strike', 'Valor Op', 'Valor Implicito'])  # lista com as PUT ITM
        self.callITM = pd.DataFrame(columns=['Strike', 'Valor Op', 'Valor Implicito'])  # lista com as CALL ITM

        self.putOTM = pd.DataFrame(columns=['Strike', 'Valor Op'])  # lista com as PUT OTM
        self.callOTM = pd.DataFrame(columns=['Strike', 'Valor Op'])  # lista com as CALL OTM

        self.sigma = 0


        self.numDiasVol = numDiasVol
        self.tempoVencimento = 0

        mt5.initialize()

        # Pegas os vencimentos para as opções adjacentes da ação
        self.listaSimbolos = mt5.symbols_get(self.ativo[0:4])

        vencimentos = []

        for l in self.listaSimbolos:
            if l.expiration_time > self.hoje.timestamp():
                exist = 0
                for v in vencimentos:
                    if v == l.expiration_time:
                        exist = 1
                if exist == 0:
                    vencimentos.append(l.expiration_time)
        vencimentos.sort()

        for v in vencimentos:
            count = 0
            for l in self.listaSimbolos:
                if l.expiration_time == v:
                    count = count + 1
            self.vencimentos = self.vencimentos.append(
                {"Vencimento": datetime.utcfromtimestamp(v).strftime('%d/%m/%Y'), "Quantidade": count, "Vencimeto_raw": v},
                ignore_index=True)
        mt5.shutdown()
            
    def get_vencimentos(self):
        return self.vencimentos
    
    def get_tempoVencimento(self):
        return self.tempoVencimento

    def get_valor_ativoBase(self):
        return self.valorAtivoBase

    def get_put(self):
        return self.put
    def get_put_otm(self):
        return self.putOTM
    def get_put_itm(self):
        return self.putITM

    def get_call(self):
        return self.call
    def get_call_otm(self):
        return self.callOTM
    def get_call_itm(self):
        return self.callITM

    def get_volHistorica(self):
        return self.sigma
    
    def atualiza_dados(self, idxVencimento, diaInicio, tipo):
        vencimento = self.vencimentos['Vencimeto_raw'][idxVencimento]
        self.tempoVencimento = ((datetime.utcfromtimestamp(vencimento) - datetime.utcnow()).days + diaInicio) / 365

        mt5.initialize()

        valBase = mt5.copy_rates_from_pos(self.ativo, mt5.TIMEFRAME_D1, diaInicio, self.numDiasVol)
        self.valorAtivoBase = valBase[len(valBase) - 1]['close']

        #calcula a volatilidade histórica do ativo
        retornos = []
        for idx, v in enumerate(valBase):
            if idx != 0:
                retornos.append(v['close'] / valBase[idx - 1]['close'])
        self.sigma = np.sqrt(self.numDiasVol) * np.std(retornos)

        # Faz uma lista das opções para o vencimento selecionado

        for l in self.listaSimbolos:
            if l.expiration_time == vencimento:
                if ((not mt5.market_book_add(l.name)) or ((tipo != "COMPRA") and (tipo != "VENDA") and (tipo != "MEDIA"))):
                    if ((tipo == "COMPRA") or (tipo == "VENDA") or (tipo == "MEDIA")):
                        print(f'ALERTA: O ativo {l.name} não pode ser adicionado!')
                    mt5.market_book_release(l.name)
                    val = mt5.copy_rates_from_pos(l.name, mt5.TIMEFRAME_D1, diaInicio, 1)
                    if val:
                        valor = val['close'][0]
                    else:
                        print(f'ALERTA: Problema na aquisição do valor de {l.name} pelo histórico.')
                else:
                    val = mt5.market_book_get(l.name)
                    if val:
                        if tipo == "VENDA":
                            val_venda = []
                            for it in val:
                                if it[0] == 1:
                                    val_venda.append(it[1])
                            if val_venda:
                                valor = min(val_venda)
                            else:
                                val = None
                                print(f'ALERTA: Problema na aquisição do valor de VENDA do ativo {l.name}')
                        elif tipo == "COMPRA":
                            val_compra = []
                            for it in val:
                                if it[0] == 2:
                                    val_compra.append(it[1])
                            if val_compra:
                                valor = max(val_compra)
                            else:
                                val = None
                                print(f'ALERTA: Problema na aquisição do valor de COMPRA do ativo {l.name}')
                        else:
                            val_compra = []
                            val_venda = []
                            for it in val:
                                if it[0] == 1:
                                    val_venda.append(it[1])
                                else:
                                    val_compra.append(it[1])
                            if val_compra and val_venda:
                                valor = (max(val_compra) + min(val_venda))/2
                            else:
                                val = None
                                print(f'ALERTA: Problema na aquisição do valor de COMPRA ou de VENDA do ativo {l.name}')
                    else:
                        print(f'ALERTA: Problema na aquisição do valor de {l.name} pelo book.')
                        val = mt5.copy_rates_from_pos(l.name, mt5.TIMEFRAME_D1, diaInicio, 1)
                        if val:
                            valor = val['close'][0]
                        else:
                            print(f'ALERTA: Problema na aquisição do valor de {l.name} pelo histórico.')    
                if val:
                    self.opcoes = self.opcoes.append(
                        {"Codigo": l.name, "Ultimo": valor, "Strike": l.option_strike,
                            "Tipo": ["CALL", "PUT"][l.option_right == 1], "Estilo": ["EU", "AM"][l.option_mode == 1]},
                        ignore_index=True)
                

        self.opcoes = self.opcoes.sort_values(by="Strike")
        self.opcoes = self.opcoes.reset_index()

       # Separa os dados
        for idx, strike in enumerate(self.opcoes['Strike'].tolist()):
            if self.opcoes['Estilo'][idx] == "EU":
                if (self.opcoes['Tipo'][idx] == "CALL"):
                    if (strike >= self.valorAtivoBase):
                        self.callOTM = self.callOTM.append(
                            {"Strike": strike, "Valor Op": self.opcoes['Ultimo'][idx]},
                            ignore_index=True)
                    else:
                        self.callITM = self.callITM.append(
                            {"Strike": strike, "Valor Op": self.opcoes['Ultimo'][idx],
                             "Valor Implicito": self.valorAtivoBase - strike}, ignore_index=True)

                    self.call = self.call.append(
                        {"Strike": strike, "Valor Op": self.opcoes['Ultimo'][idx]}, ignore_index=True)

                elif (self.opcoes['Tipo'][idx] == "PUT"):
                    if (strike < self.valorAtivoBase):
                        self.putOTM = self.putOTM.append(
                            {"Strike": strike, "Valor Op": self.opcoes['Ultimo'][idx]}, ignore_index=True)
                    else:
                        self.putITM = self.putITM.append(
                            {"Strike": strike, "Valor Op": self.opcoes['Ultimo'][idx],
                             "Valor Implicito": strike - self.valorAtivoBase}, ignore_index=True)

                    self.put = self.put.append(
                        {"Strike": strike, "Valor Op": self.opcoes['Ultimo'][idx]}, ignore_index=True)
        mt5.shutdown()
