# Load packages -----------------------------------------------------
suppressMessages(library(readxl))
suppressMessages(library(tidyverse))

# Function defination -----------------------------------------------
convert2UTF8 <- function(inFile) {
    # Detect file type
    fileTypeDetect <- system(paste0('file -L ', inFile), intern = TRUE)
    # Convert to utf-8 if it is not utf-8
    if (! grepl('UTF-8', fileTypeDetect, ignore.case = TRUE)){
        outFile <- paste0(inFile, '.utf8')
        system(paste0('iconv -f gbk -t utf-8 ', inFile, ' > ', outFile))
        return(outFile)
    } else {
        return(inFile)
    }
}

getDiscreteColor <- function(colorNum) {
    # Generate color palette for discrete variables
    # 
    # Args: 
    #     colorNum: the number of required colors
    # 
    # Return: 
    #     a vector of colors
    # 
    # Following websites may be useful when you want to change the presets:
    #     https://colorbrewer2.org
    #     https://coolors.co/palettes/trending
    #     https://color.adobe.com/zh/create/color-wheel
    # 
    # Color presets 
    palNm <- c('#1b9e77', '#d95f02', '#7570b3', '#e7298a', '#377eb8',
               '#e41a1c', '#984ea3', '#666666')
    palLt <- c('#92ecd2', '#feb781', '#cfcde4', '#f7bad9', '#b0cfe8',
               '#f5a3a4', '#d0a9d6', '#cccccc')
    palDk <- c('#0f5742', '#7e3701', '#2f2c53', '#8a0f4e', '#235176',
               '#720d0e', '#502956', '#333333')
    totalColors <- c(palNm, palLt, palDk)
    if (colorNum <= length(totalColors)) {
        colorSet <- c(palNm, palLt, palDk)
    } else {
        palNum <- ceiling(colorNum / 3)
        colorSet <- c(colorRampPalette(palNm)(palNum),
                      colorRampPalette(palLt)(palNum),
                      colorRampPalette(palDk)(palNum))
    }
    colorVec <- colorSet[1:colorNum]
    return(colorVec)
}

loadTable <- function(inFile, colType = 'guess'){
    # Load table
    # Args:
    #     inFile: valid file format are xlsx, xls, csv, txt
    #     colType: specify column types, valid options are [guess, str]
    #
    # Return:
    #     a data frame
    #
    NAVector <- c('', '#N/A', '#N/A', 'N/A', '#NA', '-1.#IND', '-1.#QNAN',
                  '-NaN', '-nan', '1.#IND', '1.#QNAN', '<NA>', 'N/A', 'NA',
                  'NULL', 'NaN', '<na>', 'n/a', 'na', 'null', 'nan')
    if (colType == 'guess'){
        col.type.txt = cols()
        col.type.xlsx = 'guess'
    } else if (colType == 'str'){
        col.type.txt = cols(.default = "c")
        col.type.xlsx = 'text'
    }
    # Check in file exists
    if (! file.exists(inFile)){
        stop(paste0('Input file do not exists: ', inFile))
    }
    fileFormat <- readxl::format_from_signature(inFile)
    if (fileFormat %in% c('xlsx', 'xls')){
        dataFrame <- read_excel(inFile, col_types = col.type.xlsx,
                                trim_ws = TRUE, na = NAVector)
    } else if (endsWith(inFile, '.csv')){
        tryCatch({
            dataFrame <- read_csv(inFile, trim_ws = TRUE,
                                  col_types = col.type.txt,
                                  locale = locale(encoding = "UTF-8"),
                                  na = NAVector)
        }, error = function(e) {
            stop(paste0(inFile, ' should be comma (,) separated plain txt file'))
        })
    } else {
        tryCatch({
            dataFrame <- read_tsv(inFile, trim_ws = TRUE,
                                  col_types = col.type.txt,
                                  locale = locale(encoding = "UTF-8"),
                                  na = NAVector)
        }, error = function(e) {
            stop(paste0(inFile, ' should be tab separated plain txt file'))
        })
    }
    # Process empty file
    if (nrow(dataFrame) == 0){
        stop('No data contained: ', inFile)
    }
    return(as.data.frame(dataFrame, check.names = FALSE))
}

loadSampleGroup <- function(inFile){
    # Load sample and group information
    #
    # Args:
    #     inFile: column names should contain [Sample, Group], case sensitive.
    #
    # Return:
    #     a data frame of Sample and Group
    # 
    # Raise errors:
    #     invalid column names
    #     sample or group contains NA
    #     repeat sample
    #
    # Load file
    sampleFrame <- loadTable(inFile, colType = 'str')
    # Columns should contain Sample and Group
    checkColumnVector <- colnames(sampleFrame)
    if (! all(c('Sample', 'Group') %in% checkColumnVector)){
        stop(paste0('Column names should contain [Sample, Group], ',
                    'case sensitive.'))
    }
    # Sample and group should not contains NA
    if (sum(is.na(sampleFrame$Sample)) > 0){
        stop('Sample should not contains NA: ', inFile)
    }
    if (sum(is.na(sampleFrame$Group)) > 0){
        stop('Group should not contains NA: ', inFile)
    }
    # Sample name shoule not repeat
    sampleVector <- sampleFrame$Sample
    repeatSampleVector <- sampleVector[duplicated(sampleVector)]
    if (length(repeatSampleVector) > 0){
        stop('Sample should not contains repeat in ', inFile, ': ',
             paste(repeatSampleVector, collapse = ', '))
    }
    # Check additional grouping
    additionalGroups <- checkColumnVector[grepl('^Group[0-9+]$', checkColumnVector)]
    if (length(additionalGroups) > 0){
        # Check NA
        for (addGroup in additionalGroups){
            if (sum(is.na(sampleFrame[, addGroup])) > 0){
                stop(addGroup, ' should not contains NA: ', inFile)
            }
        }
        # Check if same group names if exist, and samples of these are the same
        ### Generate a list of standard Group and Sample
        groupSampleFrame <- sampleFrame[, c('Sample', 'Group')]
        groupSampleList <- split(groupSampleFrame, groupSampleFrame[, 'Group'])
        groupSampleList <- lapply(groupSampleList, as.list)
        ### Check other groups
        for (addGroup in additionalGroups){
            ### Generate group:sample list
            addGroupFrame <- sampleFrame[, c('Sample', addGroup)]
            addGroupList <- split(addGroupFrame, addGroupFrame[, addGroup])
            addGroupList <- lapply(addGroupList, as.list)
            #### Check if sample list of same group are the same
            for (groupName in names(addGroupList)){
                if (! (groupName %in% names(groupSampleList))){
                    groupSampleList[[groupName]] <- addGroupList[[groupName]]
                } else {
                    mainGroupSampleVector <- groupSampleList[[groupName]]$Sample
                    addGroupSampleVector <- addGroupList[[groupName]]$Sample
                    if (length(mainGroupSampleVector) != length(addGroupSampleVector) || 
                        all(sort(mainGroupSampleVector) != sort(addGroupSampleVector))){
                        # Either diff length or same length but diff element
                        stop(paste0('This group relate to different samples in ',
                                    'different grouping: ', groupName))
                    }
                }
            }
        }
    }
    # Convert to sample frame to character, and Group to factor
    sampleFrame <- sampleFrame %>%
                   mutate(Group = factor(Group, levels = unique(Group)))
    if (length(additionalGroups) > 0){
        for (addGroup in additionalGroups){
            uniqueGroup <- unique(sampleFrame[, addGroup])
            sampleFrame[, addGroup] <- factor(sampleFrame[, addGroup],
                                              levels = uniqueGroup)
        }
    }
    return(sampleFrame)
}

loadSample <- function(inFile){
    # Load sample information
    #
    # Args:
    #     inFile: column names should contain [Sample], case sensitive.
    #
    # Return:
    #     a data frame of Sample
    # 
    # Raise errors:
    #     invalid column names
    #     sample contains NA
    #     repeat sample
    #
    # Load file
    sampleFrame <- loadTable(inFile, colType = 'str')
    # Columns should contain Sample
    if (! ('Sample' %in% colnames(sampleFrame))){
        stop(paste0('Column names should contain [Sample], ',
                    'case sensitive.'))
    }
    # Sample should not contains NA
    if (sum(is.na(sampleFrame$Sample)) > 0){
        stop('Sample should not contains NA: ', inFile)
    }
    # Sample name shoule not repeat
    sampleVector <- sampleFrame$Sample
    repeatSampleVector <- sampleVector[duplicated(sampleVector)]
    if (length(repeatSampleVector) > 0){
        stop('Sample should not contains repeat in ', inFile, ': ',
             paste(repeatSampleVector, collapse = ', '))
    }
    return(sampleFrame)
}

loadQuantData <- function(inFile){
    # Load quantitative table
    #
    # Args:
    #     inFile: the first colum is marker, and should be unique, other columns
    #             are samples. Suffix could be xlsx, xls, csv or txt.
    # Return:
    #     a data frame of quantitative data
    #
    # Load file
    dataFrame <- loadTable(inFile)
    # Check if the first column contains repeat
    markerVector <- dataFrame[, 1, drop = TRUE]
    repeatMarkerVector <- markerVector[duplicated(markerVector)]
    if (length(repeatMarkerVector) > 0){
        stop('First column shoule not contains repeat in: ', inFile, '\n    ',
             paste(repeatMarkerVector, collapse = ', '))
    }
    # First column should not contains NA
    if (sum(is.na(markerVector)) > 0){
        stop('First column should not contains NA: ', inFile)
    }
    # Convert the type of first column to character
    titleVector <- colnames(dataFrame)
    firstColumn <- titleVector[1]
    dataFrame[firstColumn] <- map(dataFrame[firstColumn], as.character)
    return(dataFrame)
}

loadIndexLabel <- function(inFile){
    # Load table of index labels
    labelFrame <- loadTable(inFile, colType = 'str')
    colnames(labelFrame)[1:2] <- c('Index', 'Label')
    # Check if the first column contains repeat
    markerVector <- labelFrame$Index
    repeatMarkerVector <- markerVector[duplicated(markerVector)]
    if (length(repeatMarkerVector) > 0){
        stop('First column shoule not contains repeat in: ', inFile, '\n    ',
             paste(repeatMarkerVector, collapse = ', '))
    }
    # Check if the second column contains repeat
    labelVector <- labelFrame$Label
    repeatLabelVector <- labelVector[duplicated(labelVector)]
    if (length(repeatLabelVector) > 0){
        stop('Second column shoule not contains repeat in: ', inFile, '\n    ',
             paste(repeatLabelVector, collapse = ', '))
    }
    # First column should not contains NA
    if (sum(is.na(markerVector)) > 0){
        stop('First column should not contains NA: ', inFile)
    }
    # Second column should not contains NA
    if (sum(is.na(labelVector)) > 0){
        stop('Second column should not contains NA: ', inFile)
    }
    return(labelFrame)
}

loadIndexAnnot <- function(inFile){
    # Load table of index labels
    annotFrame <- loadTable(inFile, colType = 'str')
    colnames(annotFrame)[1] <- 'Index'
    # Check if the first column contains repeat
    markerVector <- annotFrame$Index
    repeatMarkerVector <- markerVector[duplicated(markerVector)]
    if (length(repeatMarkerVector) > 0){
        stop('First column shoule not contains repeat in: ', inFile, '\n    ',
             paste(repeatMarkerVector, collapse = ', '))
    }
    # First column should not contains NA
    if (sum(is.na(markerVector)) > 0){
        stop('First column should not contains NA: ', inFile)
    }
    # Second column should not contains NA
    if (sum(is.na(annotFrame[, 2])) > 0){
        stop('Second column should not contains NA: ', inFile)
    }
    return(annotFrame)
}

extractSampleData <- function(dataFrame, sampleVector){
    # Extract quantitative data of needed samples
    #
    # Args:
    #     dataFrame: the first colum is marker, other columns are sample.
    #     sampleVector: a vector of sample names
    #
    # Return:
    #     a data frame of quantitative data with subset samples
    #
    titleVector <- colnames(dataFrame)
    firstColumn <- titleVector[1]
    invalidSampleVector <- sampleVector[! (sampleVector %in% titleVector)]
    if (length(invalidSampleVector) > 0){
        stop('These sample do not exist in quantitative data: ',
             paste0(invalidSampleVector, collapse = ', '))
    }
    # Extract sample data
    dataFrame <- dataFrame[, c(firstColumn, sampleVector), drop = FALSE]
    return(dataFrame)
}

normalizeSampleFrame <- function(dataFrame, diffVector){
    # 找出差异分组的 Group* 列，提取样本和分组，输出标准列名 [Sample, Group]
    # Find the group of column of diff groups, than extract the
    # column of [Sample, Group*] and rename to [Sample, Group].
    #
    # Sample Group Group1 Group2  + [M, Z]  ->  Sample Group
    # A1     A     M      X                     A1     M
    # A2     A     M      Y                     A2     M
    # B1     B     N      Z                     B1     Z
    # B2     B     O      Z                     B1     Z
    # 
    # Args:
    #     dataFrame: data frame of sample information, column name should be 
    #         [Sample, Group, Group1, Group2, ...]
    #     diffList: a list containing diff group
    # 
    # Return:
    #     data frame of [Sample, Group]
    mergedFrame = data.frame()
    for (groupName in diffVector){
        checkGroupVector <- apply(dataFrame, 2, function(x){groupName %in% x})
        matchedColumnVector <- names(checkGroupVector[checkGroupVector])
        matchedColumnVector <- matchedColumnVector[matchedColumnVector != 'Sample']
        if (length(matchedColumnVector) == 0){
            string = 'There is no column of Group* exist this group: '
            stop(paste0(string, groupName))
        } else {
            matchedColumn <- matchedColumnVector[1]
            subFrame <- dataFrame[, c('Sample', matchedColumn)]
            colnames(subFrame)[2] <- 'Group'
            # Extract records of wanted group
            subFrame <- subset(subFrame, Group == groupName)
            mergedFrame <- rbind(mergedFrame, subFrame)
        }
    }
    # Sample name shoule not repeat
    sampleVector <- mergedFrame$Sample
    repeatSampleVector <- sampleVector[duplicated(sampleVector)]
    if (length(repeatSampleVector) > 0){
        stop('Sample should not repeat in ',
             paste(diffVector, collapse = ', '))
    }
    mergedFrame <- mergedFrame %>%
                   mutate(Group = factor(Group, levels = unique(Group)))
    return(mergedFrame)
}

loadCoefficient <- function(inFile){
    # Load table of correlation coefficient and P-value
    #
    # Args:
    #     inFile: a table file, should contains at least 4 columns
    #         [Column1, Column2, Correlation, P-value]
    # Return:
    #     a data frame of [Column1, Column2, Correlation, P-value]
    # 
    # Load coefficient data
    dataFrame <- loadTable(inFile)
    dataFrame <- as.data.frame(dataFrame, check.names = FALSE)
    titleVector <- colnames(dataFrame)
    # data frame should contains at least 4 columns
    if (ncol(dataFrame) < 4){
        stop('Input file should contains at least 4 columns: ', inFile)
    }
    # Check essential columns: Correlation, P-value
    validColumnVector <- c('Correlation', 'P-value')
    ### These 2 columns should not be first 2 columns
    frontTwoColumns <- titleVector[1:2]
    if (any(validColumnVector %in% frontTwoColumns)){
        stop(paste0(paste0(validColumnVector, collapse = ', '),
                    ' should not be the first 2 columns of ', inFile, 
                    ', case sensitive.'))
    }
    ### These 2 columns should exist in other columns
    titleTailVector <- titleVector[3:length(titleVector)]
    if (! all(validColumnVector %in% titleTailVector)){
        stop(paste0(paste0(validColumnVector, collapse = ', '),
                    ' should exist in other columns (3 or more) of ', inFile, 
                    ', case sensitive.'))
    }
    # Check NA
    tmpDataFrame <- dataFrame[, c(frontTwoColumns, 'Correlation', 'P-value')]
    NACheck <- apply(is.na(tmpDataFrame), 1, any)
    if (sum(NACheck) > 0){
        print(tmpDataFrame[NACheck, ])
        stop('Empty data exist in ', inFile)
    }
    # Check data range of correlation
    corrVector <- dataFrame$Correlation
    if (class(corrVector) != 'numeric'){
        stop('Correlation should be numeric: ', inFile)
    } else if ((min(corrVector) < -1) || (max(corrVector) > 1)){
        stop('Correlation should be in the range of [-1, 1]: ', inFile)
    }
    # Check data range of P-value
    pvalueVector <- dataFrame$`P-value`
    if (class(pvalueVector) != 'numeric'){
        stop('P-value should be numeric: ', inFile)
    } else if ((min(pvalueVector) < 0) || (max(pvalueVector) > 1)){
        stop('P-value should be in the range of [0, 1]: ', inFile)
    }
    return(dataFrame)
}

loadEnrichment <- function(inFile, type = 'KEGG'){
    # Define column vectors
    if (type == 'KEGG'){
        uniqueColVector <- c('KEGG_level_1', 'KEGG_map')
    } else if (type == 'GO'){
        uniqueColVector <- c('GO_level_1', 'GO')
    } else if (type == 'IPR'){
        uniqueColVector <- c('Class', 'IPR_acc')
    }
    commonColVector <- c('Description', 'DiffRatio', 'BgRatio', 'P-value',
                         'Adjusted P-value', 'Count_all')
    # Load enrichment table
    dataFrame <- loadTable(inFile)
    checkColumnVector <- colnames(dataFrame)
    # Check columns
    missUniColVector <- uniqueColVector[! (uniqueColVector %in% checkColumnVector)]
    if (length(missUniColVector) > 0){
        string <- paste0('Column names should contain [%s], ',
                         'case sensitive.')
        stop(sprintf(string, paste0(missUniColVector, collapse = ', ')))
    }
    missCommonColVector <- commonColVector[! (commonColVector %in% checkColumnVector)]
    if (length(missCommonColVector) > 0){
        string <- paste0('Column names should contain [%s], ',
                         'case sensitive.')
        stop(sprintf(string, paste0(missCommonColVector, collapse = ', ')))
    }
    # Check NA
    mergeVector <- c(uniqueColVector, commonColVector)
    tmpFrame <- dataFrame[, mergeVector]
    NACheck <- apply(is.na(tmpFrame), 1, any)
    if (sum(NACheck) > 0){
        print(tmpFrame[NACheck, ])
        stop('Empty data exist in ', inFile)
    }
    # Description shoule not contains repeat
    descVector <- dataFrame$Description
    repeatDescVector <- descVector[duplicated(descVector)]
    if (length(repeatDescVector) > 0){
        stop('Description should not contains repeat in ', inFile, ':\n',
             paste(repeatDescVector, collapse = '\n'))
    }
    return(dataFrame)
}

generateCoefMatrix <- function(coefDataFrame){
    # Extract correlation coefficient and P-value, then convert to matrix
    #
    # Args:
    #     coefDataFrame: data frame of [Col1, Col2, Correlation, P-value]
    # Return:
    #     a list of Correlation matrix and P-value matrix
    #
    # i.e.
    #   Col1  Col2  Correlation  P-value
    #   M1    N1    0.12         0.01
    #   M1    N2    0.35         0.04
    #   M2    N1    0.75         0.08
    #   M2    N2    0.86         0.50
    #     -->
    #   Correlation matrix   +   P-value matrix
    #       N1    N2                 N1    N2
    #   M1  0.12  0.35           M1  0.01  0.04
    #   M2  0.75  0.86           M2  0.08  0.50
    #
    frontTwoColumns <- colnames(coefDataFrame)[1:2]
    # Extract correlation coefficient and convert to matrix
    coefFrame <- coefDataFrame %>%
                 select(all_of(frontTwoColumns), 'Correlation') %>%
                 pivot_wider(names_from = frontTwoColumns[2],
                             values_from = Correlation) %>%
                 as.data.frame() %>%
                 column_to_rownames(var = frontTwoColumns[1])
    # Extract P-value of correlation coefficient and convert to matrix
    pvalueFrame <- coefDataFrame %>%
                   select(all_of(frontTwoColumns), 'P-value') %>%
                   pivot_wider(names_from = frontTwoColumns[2],
                               values_from = `P-value`) %>%
                   as.data.frame() %>%
                   column_to_rownames(var = frontTwoColumns[1])
    return(list(coef = coefFrame,
                pvalue = pvalueFrame))
}

guessAndSplitVector <- function(inputVector, len = 20){
    # Split string vector by ; or |, extract unique and shortest terminal strings
    #
    # Args:
    #     inputVector: a string vector, i.e.
    #          A;B;C
    #          X;Y;C
    #          D;E;F
    #
    # Return:
    #     a vector of last element, i.e.
    #         B;C
    #         Y;C
    #         F
    #
    # Define split function
    splitVector <- function(x){
        vec <- str_split(x, fixed(sepFlag))[[1]]
        return(vec[length(vec)])
    }
    # Get needed number of data
    if (length(inputVector) > len){
        testVector <- inputVector[1:len]
    } else {
        testVector <- inputVector
    }
    # Guess the separator in input vector, normally ; or |
    if (all(grepl(';', testVector, fixed = TRUE))){
        sepFlag <- ';'
    } else if (all(grepl('|', testVector, fixed = TRUE))){
        sepFlag <- '|'
    } else {
        sepFlag <- ' '
    }
    # Check if last taxon exist repeat in unique inputVector
    lastTaxonUniVector <- sapply(inputVector, splitVector)
    repeatTaxon <- unique(lastTaxonUniVector[duplicated(lastTaxonUniVector)])
    i <- 0
    while (length(repeatTaxon) > 0){
        indices <- which(lastTaxonUniVector %in% repeatTaxon)
        i <- i + 1
        for (indice in indices){
            taxon <- str_split(inputVector[indice], fixed(sepFlag))[[1]]
            taxonShort <- paste(taxon[(length(taxon) - i):(length(taxon))], 
                                collapse = ';')
            lastTaxonUniVector[indice] <- taxonShort
        }
        repeatTaxon <- lastTaxonUniVector[duplicated(lastTaxonUniVector)]
        if (i >= length(taxon)){
            break
        }
    }
    if (length(repeatTaxon) > 0){
        warning('Last element exists repeat: ',
             paste0(repeatTaxon, collapse = ', ',
             ', risk happens if taxonomy be shortened'))
    }
    # Remove names of vector
    names(lastTaxonUniVector) <- NULL
    return(lastTaxonUniVector)
}

calcHeatmapSize = function(heatmap, unit = "inch") {
    # Calc width and height of heatmap of ComplexHeatmap
    pdf(NULL)
    heatmap = draw(heatmap)
    width = ComplexHeatmap:::width(heatmap)
    width = convertX(width, unit, valueOnly = TRUE)
    height = ComplexHeatmap:::height(heatmap)
    height = convertY(height, unit, valueOnly = TRUE)
    dev.off()
    return(list(width = width,
                height = height))
}

timeMessage <- function(text) {
    # Generate running messages with timestamp
    # Format: messages: [YYYY-MM-DD HH:MM:SS]
    #
    argv <- commandArgs(trailingOnly = FALSE)
    script <- basename(substring(argv[grep('--file=', argv)], 8))
    cat(paste0('\n', script, ' ', text, ': [', Sys.time(), ']\n\n'))
}

dataNormalise <- function(matrix, method='scale', axis='col', min=NULL, max=NULL){
    # Data normalization
    #
    # Args:
    #     matrix: data frame
    #     method: 
    #         center: values of each feature are subtracted by their mean.
    #         scale: values of each feature are mean centered and divided by the 
    #                standard deviation of the feature.
    #         range: values of each feature are scaled to the specified range min to max
    #         min_max: values of each feature are scaled to the fixed range 0 to 1
    #         mean: values of each feature are divided by their mean
    #         pareto: values of each feature are mean centered and divided by the 
    #                 variance of the feature.
    #     axis: valid options are [col, row]
    #     min/max: only available for [range] method.
    #
    rangeScale <- function(x, min = NULL, max = NULL){
        k <- (max - min)/(max(x, na.rm = TRUE) - min(x, na.rm = TRUE))
        return(min + k * (x - min(x, na.rm = TRUE)))
    }
    # Check if matrix is valid
    if (is.null(dim(matrix))){
        stop('Input data should be matrix like')
    }
    checkNumericVector <- sapply(matrix, is.numeric)
    if (sum(! checkNumericVector) > 0){
        invalidColVector <- names(checkNumericVector[! checkNumericVector])
        stop('These columns are not numeric: ',
             paste(invalidColVector, collapse = ', '))
    }
    # Check if parameters are valid
    validMethodVector <- c('center', 'scale', 'range', 'min_max', 'mean', 'pareto')
    if (! method %in% validMethodVector){
        stop('method should be one of: ',
             paste(validMethodVector, collapse = ', '))
    }
    if (! axis %in% c('row', 'col')){
        stop('axis must be one of [row, col]')
    }
    # Tranpose matrix for row normalise
    if (axis == 'row'){
        matrix <- t(matrix)
    }
    # Data preprocess
    if (method == 'center'){
        matrix <- scale(matrix, center = TRUE, scale = FALSE)
    } else if (method == 'scale'){
        matrix <- scale(matrix, center = TRUE, scale = TRUE)
    } else if (method == 'range'){
        if (is.null(min) || is.null(max)){
            stop('min/max must both be specified')
        } else if (! is.numeric(min) || ! is.numeric(max)){
            stop('min/max must both be numeric')
        } else if (min >= max){
            stop('min should be smaller than max')
        }
        matrix <- apply(matrix, 2, function(x){rangeScale(x, min = min, max = max)})
    } else if (method == 'min_max'){
        matrix <- apply(matrix, 2, function(x){rangeScale(x, min = 0, max = 1)})
    } else if (method == 'mean'){
        matrix <- apply(matrix, 2, function(x){x/mean(x, na.rm = TRUE)})
    } else if (method == 'pareto'){
        matrix <- apply(matrix, 2, function(x){(x - mean(x, na.rm = TRUE))/sqrt(sd(x, na.rm = T))})
    }
    # Return
    if (axis == 'col'){
        return(matrix)
    } else if (axis == 'row'){
        return(t(matrix))
    }
}
