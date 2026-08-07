
A intenção era utilizar o bview, não o upadte, então abandonei essa estratégia, mas por documentação deixei esse arquivo de explicação.
Consegui o arquivo "update_20250331.1600.txt" após rodar:
`
bgpscanner update_20250331.1600.gz > update_20250331.1600.txt
`
Conheci o bgpscanner por ajuda do Joaquim.
O arquivo original .gz veio de:
https://data.ris.ripe.net/rrc00/2025.03/

O que sei desse arquivo:
Ele tem atualizações nos caminhos BGP. O primeiro caracter indica se a rota 
está sendo removida (-) ou adicionada (+). 
Posso encontrar, também, casos onde tenho uma remoção logo após uma adição do mesmo caminho (de prefixo A até prefixo B), então é  
-|130.137.124.0/24|||||||80.77.16.114 34549|1740787201|1
+|130.137.124.0/24|34549 6830 174 16509|80.77.16.114|i|||6830:17000 6830:17504 6830:23001 6830:34108 34549:100 34549:6830|80.77.16.114 34549|1740787201|1


Os campos são:
operação|Prefixo|AS PATH|Next Hop|origin? (valor i, não sei o que é)|?|?|communities?|Next Hop + ASN?|timestamp|?(0 ou 1)


